"""
ABOUTME: Modal deployment script for JuraGPT OCR pipeline
ABOUTME: Handles deployment, testing, and monitoring of Modal functions
"""

import subprocess
import sys
import os
from typing import Optional


class ModalDeployer:
    """Deploy and manage Modal OCR functions"""

    def __init__(self):
        self.app_name = "juragpt-ocr"
        self.modal_file = "modal_ocr/ocr_pipeline.py"

    def check_modal_auth(self) -> bool:
        """Check if Modal CLI is authenticated"""
        try:
            result = subprocess.run(
                ["modal", "token", "list"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except FileNotFoundError:
            print("❌ Modal CLI not found. Install with: pip install modal")
            return False

    def create_secret(self, secret_name: str, env_vars: dict) -> bool:
        """
        Create Modal secret with environment variables

        Args:
            secret_name: Name of the secret (e.g., 'juragpt-secrets')
            env_vars: Dict of environment variables

        Returns:
            True if successful
        """
        print(f"Creating Modal secret: {secret_name}")

        # Modal secrets are created via CLI
        cmd = ["modal", "secret", "create", secret_name]

        for key, value in env_vars.items():
            cmd.append(f"{key}={value}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"✅ Secret '{secret_name}' created successfully")
                return True
            else:
                print(f"❌ Secret creation failed: {result.stderr}")
                return False

        except Exception as e:
            print(f"❌ Error creating secret: {str(e)}")
            return False

    def deploy(self, environment: str = "production") -> bool:
        """
        Deploy Modal functions

        Args:
            environment: Deployment environment (production/staging)

        Returns:
            True if deployment successful
        """
        print(f"\n🚀 Deploying JuraGPT OCR to Modal ({environment})...\n")

        # Check authentication
        if not self.check_modal_auth():
            print("❌ Modal authentication required. Run: modal token new")
            return False

        # Deploy the stub
        try:
            cmd = ["modal", "deploy", self.modal_file]

            if environment == "staging":
                # For staging, use different app name
                # (Modal doesn't have built-in staging, so we use naming convention)
                cmd.append("--name")
                cmd.append(f"{self.app_name}-staging")

            print(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(f"\n✅ Deployment successful!")
                print(result.stdout)

                # Print function URLs
                print("\n📍 Function endpoints:")
                print(f"  - ocr_batch: https://modal.com/apps/{self.app_name}/ocr_batch")
                print(f"  - ocr_single_page: https://modal.com/apps/{self.app_name}/ocr_single_page")

                return True
            else:
                print(f"\n❌ Deployment failed:")
                print(result.stderr)
                return False

        except Exception as e:
            print(f"❌ Deployment error: {str(e)}")
            return False

    def test_deployment(self) -> bool:
        """
        Test deployed Modal functions with sample data

        Returns:
            True if tests pass
        """
        print("\n🧪 Testing Modal deployment...\n")

        try:
            # Run the Modal function in test mode
            cmd = ["modal", "run", self.modal_file]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print("✅ Test passed!")
                print(result.stdout)
                return True
            else:
                print("❌ Test failed:")
                print(result.stderr)
                return False

        except Exception as e:
            print(f"❌ Test error: {str(e)}")
            return False

    def get_logs(self, limit: int = 50) -> Optional[str]:
        """
        Fetch recent logs from Modal

        Args:
            limit: Number of recent logs to fetch

        Returns:
            Log output or None
        """
        try:
            cmd = ["modal", "app", "logs", self.app_name, "--limit", str(limit)]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                return result.stdout
            else:
                return None

        except Exception as e:
            print(f"❌ Error fetching logs: {str(e)}")
            return None

    def get_stats(self) -> Optional[dict]:
        """
        Get usage statistics from Modal

        Returns:
            Dict with usage stats or None
        """
        try:
            cmd = ["modal", "app", "stats", self.app_name]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                print(result.stdout)
                return {"status": "success"}
            else:
                return None

        except Exception as e:
            print(f"❌ Error fetching stats: {str(e)}")
            return None


def main():
    """Main deployment script"""
    deployer = ModalDeployer()

    # Parse command line arguments
    if len(sys.argv) < 2:
        print("""
Usage:
  python modal_ocr/deploy.py [command]

Commands:
  deploy          Deploy to production
  deploy-staging  Deploy to staging
  test            Test deployed functions
  logs            Fetch recent logs
  stats           Get usage statistics
  create-secret   Create Modal secret (requires env vars)

Examples:
  python modal_ocr/deploy.py deploy
  python modal_ocr/deploy.py logs
        """)
        sys.exit(1)

    command = sys.argv[1]

    if command == "deploy":
        success = deployer.deploy(environment="production")
        sys.exit(0 if success else 1)

    elif command == "deploy-staging":
        success = deployer.deploy(environment="staging")
        sys.exit(0 if success else 1)

    elif command == "test":
        success = deployer.test_deployment()
        sys.exit(0 if success else 1)

    elif command == "logs":
        logs = deployer.get_logs(limit=100)
        if logs:
            print(logs)
            sys.exit(0)
        else:
            sys.exit(1)

    elif command == "stats":
        stats = deployer.get_stats()
        sys.exit(0 if stats else 1)

    elif command == "create-secret":
        # Read from environment or .env file
        from dotenv import load_dotenv
        load_dotenv()

        env_vars = {
            "SUPABASE_URL": os.getenv("SUPABASE_URL", ""),
            "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        }

        # Validate
        if not all(env_vars.values()):
            print("❌ Missing environment variables. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
            sys.exit(1)

        success = deployer.create_secret("juragpt-secrets", env_vars)
        sys.exit(0 if success else 1)

    else:
        print(f"❌ Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
