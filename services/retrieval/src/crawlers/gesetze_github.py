"""
ABOUTME: Crawler for kmein/gesetze GitHub repository - German laws in markdown format.
ABOUTME: Most reliable data source with no API rate limits or timeouts.
"""

import logging
import re
import subprocess
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from src.models.document import StatuteDocument

logger = logging.getLogger(__name__)


class GesetzeGitHubCrawler:
    """
    Crawler for kmein/gesetze GitHub repository.

    This repository contains all German federal laws (Bundesgesetze) in
    markdown format, extracted from official XML sources.

    Advantages:
    - No API rate limits or timeouts
    - Complete law texts with proper structure
    - Regular updates via Git
    - Can be used offline after initial clone

    Repository: https://github.com/kmein/gesetze
    License: Public domain (laws are not copyrightable)

    Usage:
        crawler = GesetzeGitHubCrawler()
        documents = crawler.fetch_laws(limit=1000)
    """

    def __init__(
        self,
        repo_url: str = "https://github.com/kmein/gesetze.git",
        cache_dir: Path = Path("data/gesetze_repo")
    ):
        """
        Initialize GitHub crawler.

        Args:
            repo_url: GitHub repository URL
            cache_dir: Local directory to clone repo into
        """
        self.repo_url = repo_url
        self.cache_dir = cache_dir
        self.laws_dir = cache_dir / "laws"  # Laws are in laws/ subdirectory

        logger.info(f"GesetzeGitHubCrawler initialized: {repo_url}")
        logger.info(f"Cache directory: {cache_dir}")

    def _clone_or_update_repo(self) -> None:
        """
        Clone repository if not exists, otherwise pull latest changes.
        """
        if not self.cache_dir.exists():
            logger.info(f"Cloning repository to {self.cache_dir}...")
            self.cache_dir.parent.mkdir(parents=True, exist_ok=True)

            # Clone with depth=1 for faster download
            subprocess.run(
                ["git", "clone", "--depth", "1", self.repo_url, str(self.cache_dir)],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Repository cloned successfully")
        else:
            logger.info("Updating existing repository...")
            subprocess.run(
                ["git", "-C", str(self.cache_dir), "pull"],
                check=True,
                capture_output=True,
                text=True
            )
            logger.info("Repository updated successfully")

    def _parse_law_file(self, file_path: Path) -> Optional[StatuteDocument]:
        """
        Parse a single law markdown file.

        File structure (actual format from kmein/gesetze markdown branch):
        # [BGB] Bürgerliches Gesetzbuch  (BGB)

        Ausfertigungsdatum: 18.08.1896

        ## § 1 - Title
        Content...

        Args:
            file_path: Path to markdown file

        Returns:
            Parsed StatuteDocument or None if parsing failed
        """
        try:
            content = file_path.read_text(encoding="utf-8")

            # Try to extract YAML frontmatter if present
            frontmatter_match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)

            if frontmatter_match:
                # Has YAML frontmatter
                frontmatter_text = frontmatter_match.group(1)
                body = frontmatter_match.group(2).strip()

                # Parse frontmatter (simple key: value format)
                frontmatter = {}
                for line in frontmatter_text.split('\n'):
                    if ':' in line:
                        key, value = line.split(':', 1)
                        frontmatter[key.strip()] = value.strip()

                title = frontmatter.get('Title', file_path.stem)
                slug = frontmatter.get('Slug', file_path.stem.lower())
            else:
                # No frontmatter - extract from first line
                # Format: # [BGB] Bürgerliches Gesetzbuch  (BGB)
                body = content.strip()
                first_line_match = re.match(r'^#\s*\[([^\]]+)\]\s*(.+)', content.split('\n')[0])

                if first_line_match:
                    slug = first_line_match.group(1).strip()
                    title = first_line_match.group(2).strip()
                else:
                    # Fallback to filename
                    slug = file_path.stem
                    title = file_path.stem

            # Remove excessive whitespace while preserving structure
            body = re.sub(r'\n{3,}', '\n\n', body)

            # Create document
            document: StatuteDocument = {
                "source": "gesetze_github",
                "type": "law",
                "slug": slug,
                "title": title,
                "content": body,
                "created_date": datetime.now().isoformat(),
                "url": f"https://github.com/kmein/gesetze/blob/markdown/laws/{file_path.name}",
            }

            return document

        except Exception as e:
            logger.error(f"Error parsing {file_path.name}: {e}")
            return None

    def fetch_laws(
        self,
        limit: Optional[int] = None,
        update_repo: bool = True
    ) -> List[StatuteDocument]:
        """
        Fetch laws from GitHub repository.

        Args:
            limit: Maximum number of laws to fetch (None = all)
            update_repo: Whether to pull latest changes

        Returns:
            List of statute documents
        """
        logger.info("Fetching laws from kmein/gesetze repository...")

        # Clone or update repository
        if update_repo:
            self._clone_or_update_repo()

        # Check if laws directory exists
        if not self.laws_dir.exists():
            logger.error(f"Laws directory not found: {self.laws_dir}")
            return []

        # Find all markdown files
        law_files = sorted(self.laws_dir.glob("*.md"))
        total_files = len(law_files)

        logger.info(f"Found {total_files} law files")

        if limit:
            law_files = law_files[:limit]
            logger.info(f"Limited to {limit} files")

        # Parse files
        documents: List[StatuteDocument] = []

        for i, file_path in enumerate(law_files, 1):
            if i % 100 == 0:
                logger.info(f"Parsed {i}/{len(law_files)} files...")

            doc = self._parse_law_file(file_path)
            if doc:
                documents.append(doc)

        logger.info(f"Successfully parsed {len(documents)}/{len(law_files)} laws")

        return documents

    def get_repo_stats(self) -> dict:
        """
        Get statistics about the repository.

        Returns:
            Dictionary with repo stats
        """
        if not self.laws_dir.exists():
            return {
                "repo_cloned": False,
                "total_laws": 0,
                "cache_size_mb": 0
            }

        law_files = list(self.laws_dir.glob("*.md"))

        # Calculate cache size
        cache_size_bytes = sum(
            f.stat().st_size
            for f in self.cache_dir.rglob("*")
            if f.is_file()
        )

        return {
            "repo_cloned": True,
            "total_laws": len(law_files),
            "cache_size_mb": cache_size_bytes / (1024 * 1024),
            "cache_path": str(self.cache_dir)
        }


def main():
    """Test the GitHub crawler."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    crawler = GesetzeGitHubCrawler()

    # Get stats
    stats = crawler.get_repo_stats()
    print("\n=== Repository Stats ===")
    for key, value in stats.items():
        print(f"{key}: {value}")

    # Fetch first 5 laws
    print("\n=== Fetching Laws ===")
    documents = crawler.fetch_laws(limit=5, update_repo=True)

    print(f"\nFetched {len(documents)} documents")

    # Show first document
    if documents:
        doc = documents[0]
        print(f"\n=== Sample Document ===")
        print(f"Title: {doc['title']}")
        print(f"Slug: {doc['slug']}")
        print(f"Source: {doc['source']}")
        print(f"Content length: {len(doc['content'])} chars")
        print(f"Content preview:\n{doc['content'][:500]}...")


if __name__ == "__main__":
    main()
