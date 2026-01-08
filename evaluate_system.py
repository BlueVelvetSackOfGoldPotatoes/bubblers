#!/usr/bin/env python3
"""
Comprehensive evaluation script for the comment bubbling system.
Analyzes clustering decisions, bubble quality, and provides recommendations.
"""

import json
import sys
from pathlib import Path

import requests

from app.evaluation import DetailedEvaluator
from app.models import PostState


def evaluate_post(post_id: str, api_base: str = "http://127.0.0.1:8000", threshold: float = 0.58) -> None:
    """
    Evaluate a post's clustering and generate detailed report.
    
    Args:
        post_id: ID of the post to evaluate
        api_base: Base URL for API
        threshold: Clustering threshold used
    """
    print(f"Fetching state for post {post_id}...")
    response = requests.get(f"{api_base}/api/posts/{post_id}/state")
    
    if not response.ok:
        print(f"Error: {response.status_code} - {response.text}")
        return
    
    state_dict = response.json()
    state = PostState(**state_dict)
    
    print(f"\n{'='*80}")
    print(f"EVALUATION REPORT")
    print(f"{'='*80}")
    print(f"Post: {state.post.title}")
    print(f"Comments: {len(state.comments)}")
    print(f"Bubbles: {len(state.bubbles)}")
    print(f"Bubble Versions: {len(state.bubble_versions)}")
    print(f"Threshold: {threshold}")
    print(f"{'='*80}\n")
    
    evaluator = DetailedEvaluator(threshold=threshold)
    
    pipeline_runs = []
    post_data_response = requests.get(f"{api_base}/api/posts/{post_id}/state")
    if post_data_response.ok:
        post_data = post_data_response.json()
        pipeline_runs = post_data.get("pipeline_runs", [])
    
    report = evaluator.evaluate(state, pipeline_runs)
    
    print("METRICS SUMMARY")
    print("-" * 80)
    for key, value in report.metrics_summary.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")
    
    print(f"\n{'='*80}")
    print("CLUSTERING DECISIONS ANALYSIS")
    print(f"{'='*80}")
    
    created_new_count = sum(1 for d in report.clustering_decisions if d.created_new_bubble)
    assigned_count = len(report.clustering_decisions) - created_new_count
    
    print(f"\nTotal decisions: {len(report.clustering_decisions)}")
    print(f"  - Created new bubbles: {created_new_count}")
    print(f"  - Assigned to existing: {assigned_count}")
    
    if report.clustering_decisions:
        similarities = [d.similarity_score for d in report.clustering_decisions if not d.created_new_bubble]
        if similarities:
            print(f"\nSimilarity scores (assigned comments):")
            print(f"  - Average: {sum(similarities)/len(similarities):.3f}")
            print(f"  - Min: {min(similarities):.3f}")
            print(f"  - Max: {max(similarities):.3f}")
        
        close_calls = [d for d in report.clustering_decisions if abs(d.similarity_score - d.threshold) < 0.05]
        print(f"\nClose calls (within 0.05 of threshold): {len(close_calls)}")
    
    print(f"\n{'='*80}")
    print("BUBBLE ANALYSES")
    print(f"{'='*80}\n")
    
    for i, analysis in enumerate(report.bubble_analyses, 1):
        print(f"Bubble {i}: {analysis.label}")
        print(f"  Size: {analysis.size} comments")
        print(f"  Cohesion: {analysis.cohesion:.3f}")
        print(f"  Avg similarity to centroid: {analysis.avg_similarity_to_centroid:.3f}")
        print(f"  Similarity range: {analysis.min_similarity:.3f} - {analysis.max_similarity:.3f}")
        
        if analysis.issues:
            print(f"  Issues:")
            for issue in analysis.issues:
                print(f"    - {issue}")
        
        if analysis.potential_merges:
            print(f"  Potential merges:")
            for merge_id, sim, label in analysis.potential_merges:
                print(f"    - With '{label}' (similarity: {sim:.3f})")
        
        if analysis.potential_splits:
            print(f"  Potential splits:")
            for cid1, cid2, sim in analysis.potential_splits[:2]:
                print(f"    - Comments with low similarity: {sim:.3f}")
        
        print()
    
    print(f"{'='*80}")
    print("THRESHOLD ANALYSIS")
    print(f"{'='*80}\n")
    
    ta = report.threshold_analysis
    print(f"Current threshold: {ta['current_threshold']:.3f}")
    print(f"Avg intra-bubble similarity: {ta['avg_intra_bubble_similarity']:.3f}")
    print(f"Avg inter-bubble similarity: {ta['avg_inter_bubble_similarity']:.3f}")
    print(f"Min intra-bubble similarity: {ta['min_intra_bubble_similarity']:.3f}")
    print(f"Max inter-bubble similarity: {ta['max_inter_bubble_similarity']:.3f}")
    
    if ta.get('suggested_thresholds'):
        for suggestion in ta['suggested_thresholds']:
            print(f"\nSuggested threshold: {suggestion['threshold']:.3f}")
            print(f"  Reasoning: {suggestion['reasoning']}")
    
    print(f"\n{'='*80}")
    print("RECOMMENDATIONS")
    print(f"{'='*80}\n")
    
    if report.recommendations:
        for i, rec in enumerate(report.recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("No specific recommendations at this time.")
    
    print(f"\n{'='*80}")
    print("VOTING ANALYSIS")
    print(f"{'='*80}\n")
    
    votes = {}
    for comment in state.comments:
        vote = comment.vote or "pass"
        votes[vote] = votes.get(vote, 0) + 1
    
    total_votes = sum(votes.values())
    if total_votes > 0:
        print(f"Total comments with votes: {total_votes}")
        for vote_type in ["agree", "disagree", "pass"]:
            count = votes.get(vote_type, 0)
            percentage = (count / total_votes * 100) if total_votes > 0 else 0
            print(f"  {vote_type}: {count} ({percentage:.1f}%)")
    
    bubble_votes = {}
    for bv in state.bubble_versions:
        bubble_votes_by_type = {"agree": 0, "disagree": 0, "pass": 0}
        for cid in bv.comment_ids:
            comment = next((c for c in state.comments if c.id == cid), None)
            if comment and comment.vote:
                bubble_votes_by_type[comment.vote] = bubble_votes_by_type.get(comment.vote, 0) + 1
        bubble_votes[bv.id] = bubble_votes_by_type
    
    print(f"\nVote distribution by bubble:")
    for bv in state.bubble_versions[:10]:
        votes = bubble_votes.get(bv.id, {})
        total = sum(votes.values())
        if total > 0:
            print(f"  '{bv.label}': agree={votes.get('agree', 0)}, disagree={votes.get('disagree', 0)}, pass={votes.get('pass', 0)}")
    
    output_file = Path(f"evaluation_report_{post_id[:8]}.json")
    DetailedEvaluator.save_report(report, str(output_file))
    print(f"\n{'='*80}")
    print(f"Detailed report saved to: {output_file}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python evaluate_system.py <post_id> [threshold]")
        print("\nTo get post_id, check the API: curl http://127.0.0.1:8000/api/posts/list")
        sys.exit(1)
    
    post_id = sys.argv[1]
    threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.58
    
    evaluate_post(post_id, threshold=threshold)

