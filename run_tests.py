#!/usr/bin/env python3
"""
Comprehensive test suite for the comment bubbling system.
Generates metrics, screenshots, and evaluation reports.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from app.metrics import MetricsCalculator, EvaluationReport
from app.reddit_parser import RedditParser


class TestRunner:
    """Run comprehensive tests and generate evaluation reports."""
    
    def __init__(self, api_base: str = "http://127.0.0.1:8000", results_dir: str = "test_results"):
        self.api_base = api_base
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(exist_ok=True)
        (self.results_dir / "screenshots").mkdir(exist_ok=True)
        (self.results_dir / "metrics").mkdir(exist_ok=True)
        (self.results_dir / "logs").mkdir(exist_ok=True)
        
        self.driver = None
        self.processing_times = []
    
    def take_screenshot(self, filename: str):
        """Note: Screenshots should be taken manually using browser tools."""
        print(f"  Screenshot note: {filename} (use browser tools to capture)")
    
    def test_reddit_import(self, reddit_file: str = "tests.txt"):
        """Test importing Reddit thread."""
        print(f"\n{'='*60}")
        print("TEST 1: Reddit Thread Import")
        print(f"{'='*60}")
        
        parser = RedditParser()
        
        with open(reddit_file, 'r', encoding='utf-8') as f:
            text = f.read()
        
        post, comments = parser.parse(text)
        print(f"Parsed: {len(comments)} comments")
        
        start_time = time.time()
        
        response = requests.post(
            f"{self.api_base}/api/posts",
            json={
                "title": post.title,
                "body": post.body,
                "created_at": post.created_at
            }
        )
        
        if not response.ok:
            print(f"Error creating post: {response.status_code}")
            return None
        
        state = response.json()
        post_id = state['post']['id']
        print(f"Created post: {post_id}")
        
        processing_times = []
        created = 0
        
        for i, comment in enumerate(comments):
            comment_start = time.time()
            
            response = requests.post(
                f"{self.api_base}/api/posts/{post_id}/comments",
                json={
                    "author": {
                        "id": comment.author.id,
                        "display_name": comment.author.display_name
                    },
                    "text": comment.text,
                    "reply_to_comment_id": comment.reply_to_comment_id,
                    "created_at": comment.created_at
                }
            )
            
            comment_time = time.time() - comment_start
            processing_times.append(comment_time)
            
            if response.ok:
                created += 1
                state = response.json()
            else:
                print(f"  Error adding comment {i+1}: {response.status_code}")
        
        total_time = time.time() - start_time
        self.processing_times = processing_times
        
        print(f"Imported {created}/{len(comments)} comments in {total_time:.2f}s")
        print(f"Avg processing time: {sum(processing_times)/len(processing_times):.3f}s")
        
        self.take_screenshot("reddit_import_final.png")
        
        return state, post_id
    
    def calculate_metrics(self, state: dict) -> EvaluationReport:
        """Calculate all metrics for the current state."""
        print(f"\n{'='*60}")
        print("Calculating Metrics")
        print(f"{'='*60}")
        
        from app.models import PostState
        
        post_state = PostState(**state)
        report = MetricsCalculator.calculate_all_metrics(post_state, self.processing_times)
        
        print(f"Clustering Metrics:")
        print(f"  Bubbles: {report.clustering.num_bubbles}")
        print(f"  Comments: {report.clustering.num_comments}")
        print(f"  Silhouette Score: {report.clustering.silhouette_score:.3f}")
        print(f"  Cohesion: {report.clustering.intra_cluster_cohesion:.3f}")
        print(f"  Separation: {report.clustering.inter_cluster_separation:.3f}")
        
        print(f"\nLabel Metrics:")
        print(f"  Avg Confidence: {report.labeling.avg_confidence:.3f}")
        print(f"  Label Uniqueness: {report.labeling.label_uniqueness:.3f}")
        
        print(f"\nTemporal Metrics:")
        print(f"  Creation Rate: {report.temporal.bubble_creation_rate:.3f}")
        print(f"  Stability: {report.temporal.bubble_stability:.3f}")
        
        return report
    
    def save_results(self, report: EvaluationReport, post_id: str = None):
        """Save all test results."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        metrics_file = self.results_dir / "metrics" / f"metrics_{timestamp}.json"
        MetricsCalculator.save_report(report, str(metrics_file))
        print(f"\nMetrics saved: {metrics_file}")
        
        summary_file = self.results_dir / "metrics" / f"summary_{timestamp}.txt"
        with open(summary_file, 'w') as f:
            f.write("EVALUATION REPORT SUMMARY\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Timestamp: {report.timestamp}\n")
            f.write(f"Post ID: {post_id or 'N/A'}\n\n")
            
            f.write("CLUSTERING METRICS\n")
            f.write("-" * 60 + "\n")
            f.write(f"Number of Bubbles: {report.clustering.num_bubbles}\n")
            f.write(f"Number of Comments: {report.clustering.num_comments}\n")
            f.write(f"Avg Comments per Bubble: {report.clustering.avg_comments_per_bubble:.2f}\n")
            f.write(f"Silhouette Score: {report.clustering.silhouette_score:.3f}\n")
            f.write(f"Intra-cluster Cohesion: {report.clustering.intra_cluster_cohesion:.3f}\n")
            f.write(f"Inter-cluster Separation: {report.clustering.inter_cluster_separation:.3f}\n")
            f.write(f"Comment Distribution Entropy: {report.clustering.comment_distribution_entropy:.3f}\n\n")
            
            f.write("LABEL METRICS\n")
            f.write("-" * 60 + "\n")
            f.write(f"Avg Label Length: {report.labeling.avg_label_length:.1f} chars\n")
            f.write(f"Avg Essence Length: {report.labeling.avg_essence_length:.1f} chars\n")
            f.write(f"Avg Confidence: {report.labeling.avg_confidence:.3f}\n")
            f.write(f"Label Uniqueness: {report.labeling.label_uniqueness:.3f}\n")
            f.write(f"Representative Coverage: {report.labeling.representative_coverage:.3f}\n\n")
            
            f.write("TEMPORAL METRICS\n")
            f.write("-" * 60 + "\n")
            f.write(f"Bubble Creation Rate: {report.temporal.bubble_creation_rate:.6f} bubbles/sec\n")
            f.write(f"Avg Bubble Lifetime: {report.temporal.avg_bubble_lifetime:.1f} seconds\n")
            f.write(f"Bubble Stability: {report.temporal.bubble_stability:.3f}\n")
            f.write(f"Temporal Coherence: {report.temporal.temporal_coherence:.3f}\n\n")
            
            f.write("SYSTEM METRICS\n")
            f.write("-" * 60 + "\n")
            f.write(f"Avg Processing Time: {report.system.avg_processing_time:.3f}s\n")
            f.write(f"Total API Calls: {report.system.total_api_calls}\n")
            f.write(f"Avg Response Time: {report.system.avg_response_time:.3f}s\n")
        
        print(f"Summary saved: {summary_file}")
    
    def run_all_tests(self):
        """Run all tests."""
        print("Starting Comprehensive Test Suite")
        print("=" * 60)
        
        state, post_id = self.test_reddit_import()
        
        if state:
            report = self.calculate_metrics(state)
            self.save_results(report, post_id)
            
            print(f"\n{'='*60}")
            print("TEST SUITE COMPLETE")
            print(f"{'='*60}")
            print(f"Results saved to: {self.results_dir}")
            print(f"\nTo capture screenshots, navigate to: {self.api_base}")
            print(f"Post ID: {post_id}")


if __name__ == "__main__":
    runner = TestRunner()
    runner.run_all_tests()

