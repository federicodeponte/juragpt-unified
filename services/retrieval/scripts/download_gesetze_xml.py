#!/usr/bin/env python3
# ABOUTME: Download and parse German federal laws from Gesetze im Internet (official source)
# ABOUTME: Provides structured XML access to all German laws (BGB, StGB, GG, HGB, etc.)

import requests
import zipfile
import io
import xml.etree.ElementTree as ET
import json
import os
import sys
from typing import Dict, List, Optional
from datetime import datetime

# Base URL for Gesetze im Internet
BASE_URL = "https://www.gesetze-im-internet.de"

# Common German Laws (can be expanded)
COMMON_LAWS = {
    'bgb': {'name': 'Bürgerliches Gesetzbuch', 'abbr': 'BGB', 'type': 'Civil Code'},
    'stgb': {'name': 'Strafgesetzbuch', 'abbr': 'StGB', 'type': 'Criminal Code'},
    'gg': {'name': 'Grundgesetz', 'abbr': 'GG', 'type': 'Constitution'},
    'hgb': {'name': 'Handelsgesetzbuch', 'abbr': 'HGB', 'type': 'Commercial Code'},
    'zpo': {'name': 'Zivilprozessordnung', 'abbr': 'ZPO', 'type': 'Civil Procedure'},
    'stpo': {'name': 'Strafprozessordnung', 'abbr': 'StPO', 'type': 'Criminal Procedure'},
    'ao': {'name': 'Abgabenordnung', 'abbr': 'AO', 'type': 'Tax Code'},
    'estg': {'name': 'Einkommensteuergesetz', 'abbr': 'EStG', 'type': 'Income Tax'},
    'ustg': {'name': 'Umsatzsteuergesetz', 'abbr': 'UStG', 'type': 'VAT'},
    'arbgg': {'name': 'Arbeitsgerichtsgesetz', 'abbr': 'ArbGG', 'type': 'Labor Court'},
    'bag': {'name': 'Bundesausbildungsförderungsgesetz', 'abbr': 'BAföG', 'type': 'Student Aid'},
}

class GermanLawDownloader:
    """Download and parse German federal laws from official source."""

    def __init__(self, cache_dir: str = "./data/gesetze_xml"):
        self.base_url = BASE_URL
        self.cache_dir = cache_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'GermanLawDownloader/1.0',
            'Accept': 'application/zip, text/html'
        })

        # Create cache directory
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

    def download_law_xml(self, law_slug: str) -> Optional[bytes]:
        """
        Download XML of a specific law.

        Args:
            law_slug: Law identifier (e.g., 'bgb', 'stgb', 'gg')

        Returns:
            XML content as bytes or None if failed
        """
        url = f"{self.base_url}/{law_slug}/xml.zip"

        print(f"⬇️  Downloading {law_slug.upper()}...")

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            print(f"✅ Downloaded {len(response.content)} bytes")
            return response.content

        except requests.exceptions.RequestException as e:
            print(f"❌ Error downloading {law_slug}: {e}")
            return None

    def extract_xml_from_zip(self, zip_content: bytes) -> Optional[str]:
        """Extract XML from zip archive."""
        try:
            with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                files = z.namelist()
                if len(files) > 0:
                    xml_content = z.read(files[0])
                    return xml_content.decode('utf-8')
        except Exception as e:
            print(f"❌ Error extracting XML: {e}")
        return None

    def parse_law_xml(self, xml_content: str) -> Dict:
        """
        Parse law XML into structured data.

        Returns:
            Dictionary with parsed law structure
        """
        try:
            root = ET.fromstring(xml_content)

            law_data = {
                'metadata': {},
                'sections': [],
                'full_text': xml_content
            }

            # Extract metadata
            for norm in root.findall('.//norm'):
                metadaten = norm.find('metadaten')
                if metadaten is not None:
                    jurabk = metadaten.find('jurabk')
                    if jurabk is not None:
                        law_data['metadata']['abbreviation'] = jurabk.text

                    enbez = metadaten.find('enbez')
                    titel = metadaten.find('titel')

                    if enbez is not None or titel is not None:
                        section = {
                            'section': enbez.text if enbez is not None else '',
                            'title': titel.text if titel is not None else ''
                        }

                        # Get section text
                        textdaten = norm.find('textdaten')
                        if textdaten is not None:
                            text_elem = textdaten.find('text')
                            if text_elem is not None:
                                # Get all text content
                                section['content'] = ''.join(text_elem.itertext())

                        if section.get('section') or section.get('title'):
                            law_data['sections'].append(section)

            return law_data

        except Exception as e:
            print(f"❌ Error parsing XML: {e}")
            return {}

    def get_law(self, law_slug: str, use_cache: bool = True) -> Optional[Dict]:
        """
        Get a specific law (download or from cache).

        Args:
            law_slug: Law identifier
            use_cache: Use cached version if available

        Returns:
            Parsed law data
        """
        cache_file = os.path.join(self.cache_dir, f"{law_slug}.json")

        # Check cache
        if use_cache and os.path.exists(cache_file):
            print(f"📂 Loading {law_slug.upper()} from cache...")
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # Download
        zip_content = self.download_law_xml(law_slug)
        if not zip_content:
            return None

        # Extract
        xml_content = self.extract_xml_from_zip(zip_content)
        if not xml_content:
            return None

        # Save raw XML
        xml_cache = os.path.join(self.cache_dir, f"{law_slug}.xml")
        with open(xml_cache, 'w', encoding='utf-8') as f:
            f.write(xml_content)
        print(f"💾 Saved XML to {xml_cache}")

        # Parse
        print(f"📖 Parsing {law_slug.upper()}...")
        law_data = self.parse_law_xml(xml_content)

        # Add metadata
        law_data['law_slug'] = law_slug
        law_data['download_date'] = datetime.now().isoformat()
        if law_slug in COMMON_LAWS:
            law_data['metadata'].update(COMMON_LAWS[law_slug])

        # Cache parsed data
        with open(cache_file, 'w', encoding='utf-8') as f:
            # Don't save full XML in JSON
            cache_data = law_data.copy()
            cache_data.pop('full_text', None)
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        print(f"💾 Saved parsed data to {cache_file}")

        return law_data

    def search_in_law(self, law_data: Dict, search_term: str) -> List[Dict]:
        """Search for a term within a law."""
        results = []
        search_lower = search_term.lower()

        for section in law_data.get('sections', []):
            content = section.get('content', '').lower()
            if search_lower in content or search_lower in section.get('title', '').lower():
                results.append(section)

        return results


def print_law_info(law_data: Dict):
    """Print law information."""
    print("\n" + "="*80)
    if 'metadata' in law_data:
        meta = law_data['metadata']
        print(f"📚 {meta.get('name', 'Unknown Law')}")
        print(f"   Abbreviation: {meta.get('abbr', 'N/A')}")
        print(f"   Type: {meta.get('type', 'N/A')}")
    print(f"   Sections: {len(law_data.get('sections', []))}")
    print(f"   Downloaded: {law_data.get('download_date', 'N/A')}")
    print("="*80)


def print_section(section: Dict, index: int = 0):
    """Print a law section."""
    print(f"\n{'─'*80}")
    print(f"📄 {section.get('section', 'Section')} - {section.get('title', 'No title')}")
    print(f"{'─'*80}")
    content = section.get('content', 'No content')
    if len(content) > 500:
        print(content[:500] + "...")
    else:
        print(content)


def interactive_mode():
    """Run in interactive mode."""
    downloader = GermanLawDownloader()

    print("\n" + "="*80)
    print("🇩🇪 German Federal Laws Downloader")
    print("="*80)
    print("Source: Gesetze im Internet (Official)")
    print("="*80)
    print("\nOptions:")
    print("1. Download a specific law")
    print("2. Download all common laws")
    print("3. Search in a law")
    print("4. List common laws")
    print("5. Exit")
    print("="*80)

    while True:
        choice = input("\nEnter your choice (1-5): ").strip()

        if choice == '1':
            print("\nEnter law slug (e.g., 'bgb', 'stgb', 'gg')")
            slug = input("Law slug: ").strip().lower()

            if not slug:
                print("❌ Invalid slug")
                continue

            law_data = downloader.get_law(slug)
            if law_data:
                print_law_info(law_data)

                show = input("\n📄 Show first 5 sections? (y/n): ").strip().lower()
                if show == 'y':
                    for i, section in enumerate(law_data.get('sections', [])[:5]):
                        print_section(section, i)

        elif choice == '2':
            print(f"\n⬇️  Downloading {len(COMMON_LAWS)} common German laws...")
            for slug in COMMON_LAWS.keys():
                law_data = downloader.get_law(slug)
                if law_data:
                    print_law_info(law_data)
            print("\n✅ All laws downloaded!")

        elif choice == '3':
            slug = input("\nLaw slug (e.g., 'bgb'): ").strip().lower()
            law_data = downloader.get_law(slug)

            if not law_data:
                print("❌ Could not load law")
                continue

            search_term = input("Search term: ").strip()
            results = downloader.search_in_law(law_data, search_term)

            print(f"\n🔍 Found {len(results)} sections containing '{search_term}'")
            for i, section in enumerate(results[:10]):
                print_section(section, i)

            if len(results) > 10:
                print(f"\n... and {len(results) - 10} more results")

        elif choice == '4':
            print("\n📚 Common German Laws:")
            print("="*80)
            for slug, info in COMMON_LAWS.items():
                print(f"  {slug:10s} - {info['abbr']:10s} - {info['name']}")
            print("="*80)

        elif choice == '5':
            print("\n👋 Goodbye!")
            break

        else:
            print("❌ Invalid choice. Please enter 1-5.")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Command-line mode
        downloader = GermanLawDownloader()

        if sys.argv[1] == 'download':
            if len(sys.argv) < 3:
                print("Usage: python download_gesetze_xml.py download <law_slug>")
                sys.exit(1)

            slug = sys.argv[2].lower()
            law_data = downloader.get_law(slug)
            if law_data:
                print(json.dumps(law_data, ensure_ascii=False, indent=2))

        elif sys.argv[1] == 'download-all':
            for slug in COMMON_LAWS.keys():
                downloader.get_law(slug)

        elif sys.argv[1] == 'search':
            if len(sys.argv) < 4:
                print("Usage: python download_gesetze_xml.py search <law_slug> <term>")
                sys.exit(1)

            slug = sys.argv[2].lower()
            term = sys.argv[3]

            law_data = downloader.get_law(slug)
            if law_data:
                results = downloader.search_in_law(law_data, term)
                print(json.dumps(results, ensure_ascii=False, indent=2))

        else:
            print("Usage:")
            print("  python download_gesetze_xml.py                    # Interactive mode")
            print("  python download_gesetze_xml.py download <slug>    # Download specific law")
            print("  python download_gesetze_xml.py download-all       # Download common laws")
            print("  python download_gesetze_xml.py search <slug> <term>  # Search in law")
    else:
        # Interactive mode
        interactive_mode()


if __name__ == "__main__":
    main()
