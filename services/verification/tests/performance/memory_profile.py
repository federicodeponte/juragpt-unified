"""
ABOUTME: Memory profiling script for Auditor API under load
ABOUTME: Monitors memory usage, heap allocations, and potential memory leaks

This script profiles memory usage of the Auditor API server:
- RSS (Resident Set Size) memory
- Heap allocations
- Memory growth over time
- Potential memory leaks

Usage:
    # Profile local server
    python tests/performance/memory_profile.py

    # Profile with custom duration
    python tests/performance/memory_profile.py --duration 600

    # Generate memory_plot.png
    python tests/performance/memory_profile.py --plot
"""

import argparse
import json
import psutil
import requests
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️  matplotlib not available, plotting disabled")


class MemoryProfiler:
    """
    Memory profiler for the Auditor API server.

    Monitors memory usage and detects potential memory leaks.
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8888",
        interval: int = 5,
        duration: int = 300
    ):
        """
        Initialize memory profiler.

        Args:
            api_url: Base URL of the API
            interval: Sampling interval in seconds
            duration: Total profiling duration in seconds
        """
        self.api_url = api_url
        self.interval = interval
        self.duration = duration
        self.samples: List[Dict] = []

    def get_process_info(self) -> Optional[Dict]:
        """Get process info for the Auditor API server."""
        try:
            # Try to find the process by port
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # Look for uvicorn or gunicorn running auditor
                    cmdline = ' '.join(proc.info['cmdline'] or [])
                    if 'auditor' in cmdline.lower() and ('uvicorn' in cmdline.lower() or 'gunicorn' in cmdline.lower()):
                        return proc.info
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Fallback: try to find by connections on port 8888
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr.port == 8888 and conn.status == 'LISTEN':
                    proc = psutil.Process(conn.pid)
                    return {'pid': proc.pid, 'name': proc.name()}

            return None
        except Exception as e:
            print(f"❌ Error finding process: {e}")
            return None

    def get_memory_stats(self, pid: int) -> Dict:
        """Get memory statistics for a process."""
        try:
            proc = psutil.Process(pid)
            mem_info = proc.memory_info()
            mem_percent = proc.memory_percent()

            return {
                'rss_mb': mem_info.rss / (1024 * 1024),  # MB
                'vms_mb': mem_info.vms / (1024 * 1024),  # MB
                'percent': mem_percent,
                'num_fds': proc.num_fds() if hasattr(proc, 'num_fds') else None,
                'num_threads': proc.num_threads(),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            print(f"❌ Error getting memory stats: {e}")
            return {}

    def send_verification_request(self) -> bool:
        """Send a verification request to keep server active."""
        try:
            request_data = {
                "answer": "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig einen Schaden verursacht.",
                "sources": [
                    {
                        "text": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit verletzt, ist zum Ersatz verpflichtet.",
                        "source_id": "bgb_823",
                        "score": 0.95
                    }
                ]
            }

            response = requests.post(
                f"{self.api_url}/verify",
                json=request_data,
                timeout=10
            )

            return response.status_code == 200
        except Exception as e:
            print(f"⚠️  Request failed: {e}")
            return False

    def profile(self) -> bool:
        """Run memory profiling."""
        print(f"🔍 Memory Profiler")
        print(f"   API URL: {self.api_url}")
        print(f"   Interval: {self.interval}s")
        print(f"   Duration: {self.duration}s")
        print()

        # Check if API is running
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            if response.status_code != 200:
                print(f"❌ API not healthy: {response.status_code}")
                return False
            print("✅ API is running")
        except Exception as e:
            print(f"❌ Cannot connect to API: {e}")
            return False

        # Find process
        proc_info = self.get_process_info()
        if not proc_info:
            print("❌ Cannot find Auditor process")
            print("   Make sure the API server is running")
            return False

        pid = proc_info['pid']
        print(f"✅ Found process: PID {pid} ({proc_info['name']})")
        print()

        # Start profiling
        print(f"📊 Starting memory profiling...")
        start_time = time.time()
        sample_count = 0

        try:
            while (time.time() - start_time) < self.duration:
                # Get memory stats
                mem_stats = self.get_memory_stats(pid)
                if not mem_stats:
                    print("❌ Process no longer exists")
                    return False

                # Send request to keep server active
                request_success = self.send_verification_request()

                # Record sample
                sample = {
                    'timestamp': datetime.now().isoformat(),
                    'elapsed_seconds': time.time() - start_time,
                    **mem_stats,
                    'request_success': request_success
                }
                self.samples.append(sample)
                sample_count += 1

                # Print progress
                if sample_count % 10 == 0:
                    print(f"   Sample {sample_count}: RSS={mem_stats['rss_mb']:.1f}MB, "
                          f"VMS={mem_stats['vms_mb']:.1f}MB, "
                          f"Mem%={mem_stats['percent']:.1f}%")

                time.sleep(self.interval)

        except KeyboardInterrupt:
            print("\n⚠️  Profiling interrupted by user")

        print(f"\n✅ Profiling completed: {sample_count} samples")
        return True

    def analyze(self) -> Dict:
        """Analyze memory profile data."""
        if not self.samples:
            return {}

        rss_values = [s['rss_mb'] for s in self.samples]
        vms_values = [s['vms_mb'] for s in self.samples]

        analysis = {
            'total_samples': len(self.samples),
            'duration_seconds': self.samples[-1]['elapsed_seconds'],
            'rss': {
                'initial_mb': rss_values[0],
                'final_mb': rss_values[-1],
                'min_mb': min(rss_values),
                'max_mb': max(rss_values),
                'avg_mb': sum(rss_values) / len(rss_values),
                'growth_mb': rss_values[-1] - rss_values[0],
                'growth_percent': ((rss_values[-1] - rss_values[0]) / rss_values[0]) * 100
            },
            'vms': {
                'initial_mb': vms_values[0],
                'final_mb': vms_values[-1],
                'growth_mb': vms_values[-1] - vms_values[0],
            },
            'threads': {
                'initial': self.samples[0].get('num_threads'),
                'final': self.samples[-1].get('num_threads'),
            }
        }

        # Detect potential memory leak
        growth_rate = analysis['rss']['growth_mb'] / (analysis['duration_seconds'] / 60)  # MB per minute
        if growth_rate > 10:  # > 10 MB/min growth
            analysis['warning'] = f"⚠️  High memory growth rate: {growth_rate:.2f} MB/min"
        elif growth_rate > 5:
            analysis['warning'] = f"⚠️  Moderate memory growth: {growth_rate:.2f} MB/min"
        else:
            analysis['warning'] = None

        return analysis

    def print_analysis(self):
        """Print analysis results."""
        analysis = self.analyze()
        if not analysis:
            print("❌ No data to analyze")
            return

        print("\n" + "="*60)
        print("📊 MEMORY PROFILE ANALYSIS")
        print("="*60)
        print(f"\n⏱️  Duration: {analysis['duration_seconds']:.1f}s ({len(self.samples)} samples)")

        print(f"\n📈 RSS Memory (Resident Set Size):")
        print(f"   Initial:  {analysis['rss']['initial_mb']:.1f} MB")
        print(f"   Final:    {analysis['rss']['final_mb']:.1f} MB")
        print(f"   Min:      {analysis['rss']['min_mb']:.1f} MB")
        print(f"   Max:      {analysis['rss']['max_mb']:.1f} MB")
        print(f"   Average:  {analysis['rss']['avg_mb']:.1f} MB")
        print(f"   Growth:   {analysis['rss']['growth_mb']:+.1f} MB ({analysis['rss']['growth_percent']:+.1f}%)")

        print(f"\n📦 VMS Memory (Virtual Memory Size):")
        print(f"   Initial:  {analysis['vms']['initial_mb']:.1f} MB")
        print(f"   Final:    {analysis['vms']['final_mb']:.1f} MB")
        print(f"   Growth:   {analysis['vms']['growth_mb']:+.1f} MB")

        print(f"\n🧵 Threads:")
        print(f"   Initial:  {analysis['threads']['initial']}")
        print(f"   Final:    {analysis['threads']['final']}")

        if analysis['warning']:
            print(f"\n{analysis['warning']}")
        else:
            print(f"\n✅ Memory growth is within normal limits")

        print("\n" + "="*60)

    def save_data(self, filepath: str = "tests/performance/memory_profile.json"):
        """Save profiling data to JSON file."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        data = {
            'metadata': {
                'api_url': self.api_url,
                'interval': self.interval,
                'duration': self.duration,
                'timestamp': datetime.now().isoformat(),
            },
            'samples': self.samples,
            'analysis': self.analyze()
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"💾 Data saved to: {filepath}")

    def plot(self, filepath: str = "tests/performance/memory_profile.png"):
        """Generate memory usage plot."""
        if not MATPLOTLIB_AVAILABLE:
            print("❌ matplotlib not available, cannot generate plot")
            return

        if not self.samples:
            print("❌ No data to plot")
            return

        timestamps = [s['elapsed_seconds'] / 60 for s in self.samples]  # Minutes
        rss_values = [s['rss_mb'] for s in self.samples]
        vms_values = [s['vms_mb'] for s in self.samples]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # RSS plot
        ax1.plot(timestamps, rss_values, 'b-', linewidth=2, label='RSS Memory')
        ax1.set_xlabel('Time (minutes)')
        ax1.set_ylabel('Memory (MB)')
        ax1.set_title('Auditor API - RSS Memory Usage Over Time')
        ax1.grid(True, alpha=0.3)
        ax1.legend()

        # VMS plot
        ax2.plot(timestamps, vms_values, 'g-', linewidth=2, label='VMS Memory')
        ax2.set_xlabel('Time (minutes)')
        ax2.set_ylabel('Memory (MB)')
        ax2.set_title('Auditor API - Virtual Memory Size Over Time')
        ax2.grid(True, alpha=0.3)
        ax2.legend()

        plt.tight_layout()

        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(filepath, dpi=150)
        print(f"📊 Plot saved to: {filepath}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Memory profiler for Auditor API"
    )
    parser.add_argument(
        '--url',
        default='http://localhost:8888',
        help='API base URL (default: http://localhost:8888)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Sampling interval in seconds (default: 5)'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=300,
        help='Profiling duration in seconds (default: 300)'
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help='Generate memory usage plot'
    )
    parser.add_argument(
        '--output',
        default='tests/performance/memory_profile',
        help='Output file prefix (default: tests/performance/memory_profile)'
    )

    args = parser.parse_args()

    profiler = MemoryProfiler(
        api_url=args.url,
        interval=args.interval,
        duration=args.duration
    )

    # Run profiling
    success = profiler.profile()
    if not success:
        sys.exit(1)

    # Analyze and print results
    profiler.print_analysis()

    # Save data
    profiler.save_data(f"{args.output}.json")

    # Generate plot if requested
    if args.plot:
        profiler.plot(f"{args.output}.png")

    # Check for memory leaks
    analysis = profiler.analyze()
    if analysis.get('warning'):
        print(f"\n⚠️  Warning: {analysis['warning']}")
        sys.exit(2)

    print("\n✅ Memory profiling completed successfully")
    sys.exit(0)


if __name__ == '__main__':
    main()
