from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple

from app.models import BubbleVersion, Comment, PostState
from app.utils import cosine_similarity


@dataclass
class ClusteringDecision:
    comment_id: str
    comment_text: str
    assigned_bubble_id: str
    similarity_score: float
    threshold: float
    created_new_bubble: bool
    alternative_bubbles: List[Tuple[str, float, str]]
    reasoning: str


@dataclass
class BubbleAnalysis:
    bubble_id: str
    label: str
    size: int
    cohesion: float
    avg_similarity_to_centroid: float
    min_similarity: float
    max_similarity: float
    comment_texts: List[str]
    representative_comments: List[str]
    potential_merges: List[Tuple[str, float, str]]
    potential_splits: List[Tuple[str, str, float]]
    issues: List[str]


@dataclass
class DetailedEvaluationReport:
    clustering_decisions: List[ClusteringDecision]
    bubble_analyses: List[BubbleAnalysis]
    threshold_analysis: Dict[str, any]
    recommendations: List[str]
    metrics_summary: Dict[str, float]


class DetailedEvaluator:
    """
    Comprehensive evaluator that analyzes clustering decisions, bubble quality,
    and provides actionable recommendations.
    """

    def __init__(self, threshold: float = 0.58):
        self.threshold = threshold

    def evaluate(self, state: PostState, pipeline_runs: List[any] = None) -> DetailedEvaluationReport:
        """
        Perform detailed evaluation of the clustering system.
        
        Args:
            state: Current PostState to evaluate
            pipeline_runs: Optional list of PipelineRun objects for decision history
            
        Returns:
            DetailedEvaluationReport with comprehensive analysis
        """
        comments_by_id = {c.id: c for c in state.comments}
        bubbles_by_id = {b.id: b for b in state.bubbles}
        bubble_versions_by_id = {bv.id: bv for bv in state.bubble_versions}
        
        clustering_decisions = self._analyze_clustering_decisions(
            state, comments_by_id, bubbles_by_id, bubble_versions_by_id, pipeline_runs
        )
        
        bubble_analyses = self._analyze_bubbles(
            state, comments_by_id, bubbles_by_id, bubble_versions_by_id
        )
        
        threshold_analysis = self._analyze_threshold(
            state, comments_by_id, bubbles_by_id, bubble_versions_by_id
        )
        
        recommendations = self._generate_recommendations(
            clustering_decisions, bubble_analyses, threshold_analysis
        )
        
        metrics_summary = self._calculate_summary_metrics(state)
        
        return DetailedEvaluationReport(
            clustering_decisions=clustering_decisions,
            bubble_analyses=bubble_analyses,
            threshold_analysis=threshold_analysis,
            recommendations=recommendations,
            metrics_summary=metrics_summary
        )

    def _analyze_clustering_decisions(
        self,
        state: PostState,
        comments_by_id: Dict[str, Comment],
        bubbles_by_id: Dict[str, any],
        bubble_versions_by_id: Dict[str, BubbleVersion],
        pipeline_runs: List[any]
    ) -> List[ClusteringDecision]:
        """Analyze each clustering decision made during processing."""
        decisions = []
        
        for comment in state.comments:
            if not comment.assigned_bubble_id:
                continue
            
            assigned_bubble_id = comment.assigned_bubble_id
            assigned_bv = None
            for bv in state.bubble_versions:
                if bv.bubble_id == assigned_bubble_id and comment.id in bv.comment_ids:
                    assigned_bv = bv
                    break
            
            if not assigned_bv:
                continue
            
            similarity = cosine_similarity(
                comment.embedding.vector,
                assigned_bv.centroid_embedding.vector
            )
            
            alternative_bubbles = []
            for other_bubble in bubbles_by_id.values():
                if other_bubble.id == assigned_bubble_id or not other_bubble.is_active:
                    continue
                other_bv = bubble_versions_by_id.get(other_bubble.latest_bubble_version_id)
                if not other_bv:
                    continue
                alt_sim = cosine_similarity(
                    comment.embedding.vector,
                    other_bv.centroid_embedding.vector
                )
                alternative_bubbles.append((other_bubble.id, alt_sim, other_bv.label))
            
            alternative_bubbles.sort(key=lambda x: x[1], reverse=True)
            
            created_new = assigned_bubble_id not in [b.id for b in state.bubbles if b.id != assigned_bubble_id]
            
            reasoning = self._generate_decision_reasoning(
                similarity, self.threshold, created_new, alternative_bubbles
            )
            
            decisions.append(ClusteringDecision(
                comment_id=comment.id,
                comment_text=comment.text[:200],
                assigned_bubble_id=assigned_bubble_id,
                similarity_score=similarity,
                threshold=self.threshold,
                created_new_bubble=created_new,
                alternative_bubbles=alternative_bubbles[:5],
                reasoning=reasoning
            ))
        
        return decisions

    def _analyze_bubbles(
        self,
        state: PostState,
        comments_by_id: Dict[str, Comment],
        bubbles_by_id: Dict[str, any],
        bubble_versions_by_id: Dict[str, BubbleVersion]
    ) -> List[BubbleAnalysis]:
        """Analyze each bubble for quality, cohesion, and potential issues."""
        analyses = []
        
        for bubble in state.bubbles:
            if not bubble.is_active:
                continue
            
            bv = bubble_versions_by_id.get(bubble.latest_bubble_version_id)
            if not bv:
                continue
            
            comment_embeddings = [
                comments_by_id[cid].embedding.vector
                for cid in bv.comment_ids
                if cid in comments_by_id
            ]
            
            if not comment_embeddings:
                continue
            
            similarities_to_centroid = [
                cosine_similarity(emb, bv.centroid_embedding.vector)
                for emb in comment_embeddings
            ]
            
            avg_sim = sum(similarities_to_centroid) / len(similarities_to_centroid)
            min_sim = min(similarities_to_centroid)
            max_sim = max(similarities_to_centroid)
            
            pairwise_similarities = []
            for i, emb1 in enumerate(comment_embeddings):
                for j, emb2 in enumerate(comment_embeddings):
                    if i < j:
                        pairwise_similarities.append(cosine_similarity(emb1, emb2))
            
            cohesion = sum(pairwise_similarities) / len(pairwise_similarities) if pairwise_similarities else 0.0
            
            potential_merges = []
            for other_bubble in state.bubbles:
                if other_bubble.id == bubble.id or not other_bubble.is_active:
                    continue
                other_bv = bubble_versions_by_id.get(other_bubble.latest_bubble_version_id)
                if not other_bv:
                    continue
                merge_sim = cosine_similarity(
                    bv.centroid_embedding.vector,
                    other_bv.centroid_embedding.vector
                )
                if merge_sim >= self.threshold * 0.9:
                    potential_merges.append((other_bubble.id, merge_sim, other_bv.label))
            
            potential_merges.sort(key=lambda x: x[1], reverse=True)
            
            potential_splits = []
            if len(bv.comment_ids) > 2:
                for i, cid1 in enumerate(bv.comment_ids):
                    for j, cid2 in enumerate(bv.comment_ids):
                        if i < j and cid1 in comments_by_id and cid2 in comments_by_id:
                            sim = cosine_similarity(
                                comments_by_id[cid1].embedding.vector,
                                comments_by_id[cid2].embedding.vector
                            )
                            if sim < self.threshold * 0.7:
                                potential_splits.append((cid1, cid2, sim))
            
            issues = []
            if cohesion < 0.5:
                issues.append(f"Low cohesion ({cohesion:.2f}) - comments may not belong together")
            if min_sim < self.threshold * 0.7:
                issues.append(f"Some comments have low similarity to centroid ({min_sim:.2f})")
            if len(potential_merges) > 0:
                issues.append(f"Potential merge candidates found: {len(potential_merges)}")
            if len(bv.comment_ids) == 1:
                issues.append("Single-comment bubble - consider merging")
            
            analyses.append(BubbleAnalysis(
                bubble_id=bubble.id,
                label=bv.label,
                size=len(bv.comment_ids),
                cohesion=cohesion,
                avg_similarity_to_centroid=avg_sim,
                min_similarity=min_sim,
                max_similarity=max_sim,
                comment_texts=[comments_by_id[cid].text[:100] for cid in bv.comment_ids if cid in comments_by_id],
                representative_comments=[comments_by_id[cid].text[:100] for cid in bv.representative_comment_ids if cid in comments_by_id],
                potential_merges=potential_merges[:3],
                potential_splits=potential_splits[:3],
                issues=issues
            ))
        
        return analyses

    def _analyze_threshold(
        self,
        state: PostState,
        comments_by_id: Dict[str, Comment],
        bubbles_by_id: Dict[str, any],
        bubble_versions_by_id: Dict[str, BubbleVersion]
    ) -> Dict[str, any]:
        """Analyze how different thresholds would affect clustering."""
        all_similarities = []
        intra_bubble_sims = []
        inter_bubble_sims = []
        
        for bv1 in state.bubble_versions:
            for bv2 in state.bubble_versions:
                sim = cosine_similarity(
                    bv1.centroid_embedding.vector,
                    bv2.centroid_embedding.vector
                )
                all_similarities.append(sim)
                if bv1.bubble_id == bv2.bubble_id:
                    intra_bubble_sims.append(sim)
                else:
                    inter_bubble_sims.append(sim)
        
        threshold_suggestions = []
        if intra_bubble_sims and inter_bubble_sims:
            min_intra = min(intra_bubble_sims) if intra_bubble_sims else 0.0
            max_inter = max(inter_bubble_sims) if inter_bubble_sims else 0.0
            optimal_threshold = (min_intra + max_inter) / 2.0
            
            threshold_suggestions.append({
                "threshold": optimal_threshold,
                "reasoning": f"Optimal separation point between intra-cluster ({min_intra:.3f}) and inter-cluster ({max_inter:.3f}) similarities"
            })
        
        return {
            "current_threshold": self.threshold,
            "avg_intra_bubble_similarity": sum(intra_bubble_sims) / len(intra_bubble_sims) if intra_bubble_sims else 0.0,
            "avg_inter_bubble_similarity": sum(inter_bubble_sims) / len(inter_bubble_sims) if inter_bubble_sims else 0.0,
            "min_intra_bubble_similarity": min(intra_bubble_sims) if intra_bubble_sims else 0.0,
            "max_inter_bubble_similarity": max(inter_bubble_sims) if inter_bubble_sims else 0.0,
            "suggested_thresholds": threshold_suggestions
        }

    def _generate_decision_reasoning(
        self,
        similarity: float,
        threshold: float,
        created_new: bool,
        alternatives: List[Tuple[str, float, str]]
    ) -> str:
        """Generate human-readable reasoning for a clustering decision."""
        if created_new:
            if alternatives:
                best_alt = alternatives[0]
                return f"Created new bubble. Best alternative was '{best_alt[2]}' with similarity {best_alt[1]:.3f} (below threshold {threshold:.3f})"
            return f"Created new bubble (first comment or no suitable matches)"
        else:
            margin = similarity - threshold
            if alternatives:
                best_alt = alternatives[0]
                margin_to_alt = similarity - best_alt[1]
                return f"Assigned to bubble with similarity {similarity:.3f} (threshold: {threshold:.3f}, margin: {margin:.3f}). Next best: '{best_alt[2]}' at {best_alt[1]:.3f} (margin: {margin_to_alt:.3f})"
            return f"Assigned to bubble with similarity {similarity:.3f} (threshold: {threshold:.3f}, margin: {margin:.3f})"

    def _generate_recommendations(
        self,
        decisions: List[ClusteringDecision],
        analyses: List[BubbleAnalysis],
        threshold_analysis: Dict[str, any]
    ) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        single_comment_bubbles = [a for a in analyses if a.size == 1]
        if len(single_comment_bubbles) > len(analyses) * 0.3:
            recommendations.append(
                f"High number of single-comment bubbles ({len(single_comment_bubbles)}/{len(analyses)}). "
                f"Consider lowering threshold from {self.threshold:.3f} to encourage more merging."
            )
        
        low_cohesion_bubbles = [a for a in analyses if a.cohesion < 0.5]
        if low_cohesion_bubbles:
            recommendations.append(
                f"{len(low_cohesion_bubbles)} bubbles have low cohesion (<0.5). "
                f"These may contain unrelated comments and could benefit from splitting."
            )
        
        potential_merges = sum(len(a.potential_merges) for a in analyses)
        if potential_merges > 0:
            recommendations.append(
                f"Found {potential_merges} potential merge opportunities. "
                f"Consider reviewing these bubbles for consolidation."
            )
        
        if threshold_analysis.get("suggested_thresholds"):
            suggested = threshold_analysis["suggested_thresholds"][0]["threshold"]
            if abs(suggested - self.threshold) > 0.05:
                recommendations.append(
                    f"Consider adjusting threshold from {self.threshold:.3f} to {suggested:.3f} "
                    f"for better separation between clusters."
                )
        
        close_calls = [d for d in decisions if abs(d.similarity_score - d.threshold) < 0.05]
        if len(close_calls) > len(decisions) * 0.2:
            recommendations.append(
                f"Many decisions ({len(close_calls)}) are close to threshold. "
                f"System may be sensitive to small embedding variations."
            )
        
        return recommendations

    def _calculate_summary_metrics(self, state: PostState) -> Dict[str, float]:
        """Calculate summary metrics for quick overview."""
        from app.metrics import MetricsCalculator
        
        report = MetricsCalculator.calculate_all_metrics(state)
        
        return {
            "num_bubbles": report.clustering.num_bubbles,
            "num_comments": report.clustering.num_comments,
            "avg_comments_per_bubble": report.clustering.avg_comments_per_bubble,
            "silhouette_score": report.clustering.silhouette_score,
            "cohesion": report.clustering.intra_cluster_cohesion,
            "separation": report.clustering.inter_cluster_separation,
            "label_uniqueness": report.labeling.label_uniqueness,
            "avg_confidence": report.labeling.avg_confidence
        }

    @staticmethod
    def save_report(report: DetailedEvaluationReport, filepath: str) -> None:
        """Save detailed evaluation report to JSON file."""
        def serialize(obj):
            if isinstance(obj, (ClusteringDecision, BubbleAnalysis)):
                return asdict(obj)
            return obj
        
        with open(filepath, 'w') as f:
            json.dump({
                "clustering_decisions": [asdict(d) for d in report.clustering_decisions],
                "bubble_analyses": [asdict(a) for a in report.bubble_analyses],
                "threshold_analysis": report.threshold_analysis,
                "recommendations": report.recommendations,
                "metrics_summary": report.metrics_summary
            }, f, indent=2)

