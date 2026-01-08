from __future__ import annotations

import json
import math
from dataclasses import dataclass, asdict
from typing import Dict, List

from app.models import BubbleVersion, Comment, PostState
from app.utils import cosine_similarity


@dataclass
class ClusteringMetrics:
    num_bubbles: int
    num_comments: int
    avg_comments_per_bubble: float
    max_comments_per_bubble: int
    min_comments_per_bubble: int
    bubble_size_std: float
    silhouette_score: float
    intra_cluster_cohesion: float
    inter_cluster_separation: float
    comment_distribution_entropy: float


@dataclass
class LabelMetrics:
    avg_label_length: float
    avg_essence_length: float
    avg_confidence: float
    label_uniqueness: float
    representative_coverage: float


@dataclass
class TemporalMetrics:
    bubble_creation_rate: float
    avg_bubble_lifetime: float
    bubble_stability: float
    temporal_coherence: float


@dataclass
class SystemMetrics:
    avg_processing_time: float
    total_api_calls: int
    avg_response_time: float


@dataclass
class EvaluationReport:
    clustering: ClusteringMetrics
    labeling: LabelMetrics
    temporal: TemporalMetrics
    system: SystemMetrics
    timestamp: str


class MetricsCalculator:
    """
    Calculate evaluation metrics for the comment bubbling system.
    
    Follows SOTA practices for clustering and NLP evaluation.
    """
    
    @staticmethod
    def calculate_all_metrics(state: PostState, processing_times: List[float] = None) -> EvaluationReport:
        """Calculate all metrics for a given state."""
        clustering = MetricsCalculator._calculate_clustering_metrics(state)
        labeling = MetricsCalculator._calculate_label_metrics(state)
        temporal = MetricsCalculator._calculate_temporal_metrics(state)
        system = MetricsCalculator._calculate_system_metrics(processing_times or [])
        
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).isoformat()
        
        return EvaluationReport(
            clustering=clustering,
            labeling=labeling,
            temporal=temporal,
            system=system,
            timestamp=timestamp
        )
    
    @staticmethod
    def _calculate_clustering_metrics(state: PostState) -> ClusteringMetrics:
        """Calculate clustering quality metrics."""
        comments = state.comments
        bubbles = state.bubbles
        bubble_versions = state.bubble_versions
        
        num_comments = len(comments)
        num_bubbles = len(bubbles)
        
        if num_comments == 0:
            return ClusteringMetrics(
                num_bubbles=0, num_comments=0, avg_comments_per_bubble=0.0,
                max_comments_per_bubble=0, min_comments_per_bubble=0,
                bubble_size_std=0.0, silhouette_score=0.0,
                intra_cluster_cohesion=0.0, inter_cluster_separation=0.0,
                comment_distribution_entropy=0.0
            )
        
        bubble_sizes = [len(bv.comment_ids) for bv in bubble_versions]
        if not bubble_sizes:
            bubble_sizes = [0]
        
        avg_size = sum(bubble_sizes) / len(bubble_sizes) if bubble_sizes else 0.0
        max_size = max(bubble_sizes) if bubble_sizes else 0
        min_size = min(bubble_sizes) if bubble_sizes else 0
        
        variance = sum((x - avg_size) ** 2 for x in bubble_sizes) / len(bubble_sizes) if bubble_sizes else 0.0
        std = math.sqrt(variance)
        
        silhouette = MetricsCalculator._calculate_silhouette_score(state)
        cohesion = MetricsCalculator._calculate_intra_cluster_cohesion(state)
        separation = MetricsCalculator._calculate_inter_cluster_separation(state)
        entropy = MetricsCalculator._calculate_comment_distribution_entropy(bubble_sizes, num_comments)
        
        return ClusteringMetrics(
            num_bubbles=num_bubbles,
            num_comments=num_comments,
            avg_comments_per_bubble=avg_size,
            max_comments_per_bubble=max_size,
            min_comments_per_bubble=min_size,
            bubble_size_std=std,
            silhouette_score=silhouette,
            intra_cluster_cohesion=cohesion,
            inter_cluster_separation=separation,
            comment_distribution_entropy=entropy
        )
    
    @staticmethod
    def _calculate_silhouette_score(state: PostState) -> float:
        """Calculate silhouette score for clustering quality."""
        comments = {c.id: c for c in state.comments}
        bubble_versions = state.bubble_versions
        
        if len(bubble_versions) < 2:
            return 0.0
        
        silhouette_scores = []
        
        for bv in bubble_versions:
            if not bv.comment_ids:
                continue
            
            bubble_embeddings = [comments[cid].embedding.vector for cid in bv.comment_ids if cid in comments]
            if not bubble_embeddings:
                continue
            
            for i, cid in enumerate(bv.comment_ids):
                if cid not in comments:
                    continue
                
                comment_emb = comments[cid].embedding.vector
                
                same_bubble_embs = [emb for j, emb in enumerate(bubble_embeddings) if j != i]
                if same_bubble_embs:
                    a_i = sum(cosine_similarity(comment_emb, emb) for emb in same_bubble_embs) / len(same_bubble_embs)
                else:
                    a_i = 0.0
                
                other_bubbles = [other_bv for other_bv in bubble_versions if other_bv.id != bv.id and other_bv.comment_ids]
                if other_bubbles:
                    b_scores = []
                    for other_bv in other_bubbles:
                        other_embs = [comments[oid].embedding.vector for oid in other_bv.comment_ids if oid in comments]
                        if other_embs:
                            avg_sim = sum(cosine_similarity(comment_emb, emb) for emb in other_embs) / len(other_embs)
                            b_scores.append(avg_sim)
                    b_i = min(b_scores) if b_scores else 0.0
                else:
                    b_i = 0.0
                
                if max(a_i, b_i) > 0:
                    s_i = (b_i - a_i) / max(a_i, b_i)
                    silhouette_scores.append(s_i)
        
        return sum(silhouette_scores) / len(silhouette_scores) if silhouette_scores else 0.0
    
    @staticmethod
    def _calculate_intra_cluster_cohesion(state: PostState) -> float:
        """Calculate average intra-cluster similarity (cohesion)."""
        comments = {c.id: c for c in state.comments}
        bubble_versions = state.bubble_versions
        
        cohesion_scores = []
        
        for bv in bubble_versions:
            if len(bv.comment_ids) < 2:
                continue
            
            embeddings = [comments[cid].embedding.vector for cid in bv.comment_ids if cid in comments]
            if len(embeddings) < 2:
                continue
            
            similarities = []
            for i, emb1 in enumerate(embeddings):
                for j, emb2 in enumerate(embeddings):
                    if i < j:
                        sim = cosine_similarity(emb1, emb2)
                        similarities.append(sim)
            
            if similarities:
                cohesion_scores.append(sum(similarities) / len(similarities))
        
        return sum(cohesion_scores) / len(cohesion_scores) if cohesion_scores else 0.0
    
    @staticmethod
    def _calculate_inter_cluster_separation(state: PostState) -> float:
        """Calculate average inter-cluster distance (separation)."""
        bubble_versions = state.bubble_versions
        
        if len(bubble_versions) < 2:
            return 0.0
        
        separations = []
        
        for i, bv1 in enumerate(bubble_versions):
            for j, bv2 in enumerate(bubble_versions):
                if i < j and bv1.centroid_embedding.vector and bv2.centroid_embedding.vector:
                    sim = cosine_similarity(bv1.centroid_embedding.vector, bv2.centroid_embedding.vector)
                    separations.append(1.0 - sim)
        
        return sum(separations) / len(separations) if separations else 0.0
    
    @staticmethod
    def _calculate_comment_distribution_entropy(bubble_sizes: List[int], total_comments: int) -> float:
        """Calculate entropy of comment distribution across bubbles."""
        if total_comments == 0:
            return 0.0
        
        entropy = 0.0
        for size in bubble_sizes:
            if size > 0:
                p = size / total_comments
                entropy -= p * math.log2(p)
        
        return entropy
    
    @staticmethod
    def _calculate_label_metrics(state: PostState) -> LabelMetrics:
        """Calculate label quality metrics."""
        bubble_versions = state.bubble_versions
        
        if not bubble_versions:
            return LabelMetrics(
                avg_label_length=0.0, avg_essence_length=0.0, avg_confidence=0.0,
                label_uniqueness=0.0, representative_coverage=0.0
            )
        
        labels = [bv.label for bv in bubble_versions if bv.label]
        essences = [bv.essence for bv in bubble_versions if bv.essence]
        confidences = [bv.confidence for bv in bubble_versions]
        
        avg_label_len = sum(len(l) for l in labels) / len(labels) if labels else 0.0
        avg_essence_len = sum(len(e) for e in essences) / len(essences) if essences else 0.0
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        
        unique_labels = len(set(labels))
        label_uniqueness = unique_labels / len(labels) if labels else 0.0
        
        total_reps = sum(len(bv.representative_comment_ids) for bv in bubble_versions)
        total_comments = sum(len(bv.comment_ids) for bv in bubble_versions)
        rep_coverage = total_reps / total_comments if total_comments > 0 else 0.0
        
        return LabelMetrics(
            avg_label_length=avg_label_len,
            avg_essence_length=avg_essence_len,
            avg_confidence=avg_conf,
            label_uniqueness=label_uniqueness,
            representative_coverage=rep_coverage
        )
    
    @staticmethod
    def _calculate_temporal_metrics(state: PostState) -> TemporalMetrics:
        """Calculate temporal evolution metrics."""
        from datetime import datetime
        
        bubble_versions = state.bubble_versions
        if not bubble_versions:
            return TemporalMetrics(
                bubble_creation_rate=0.0, avg_bubble_lifetime=0.0,
                bubble_stability=0.0, temporal_coherence=0.0
            )
        
        try:
            times = []
            for bv in bubble_versions:
                dt = datetime.fromisoformat(bv.created_at.replace('Z', '+00:00'))
                times.append(dt.timestamp())
            
            if len(times) < 2:
                return TemporalMetrics(0.0, 0.0, 0.0, 0.0)
            
            times.sort()
            time_span = times[-1] - times[0]
            creation_rate = len(bubble_versions) / time_span if time_span > 0 else 0.0
            
            bubble_lifetimes = []
            bubbles_by_id = {b.id: b for b in state.bubbles}
            for bubble in bubbles_by_id.values():
                bubble_versions_list = [bv for bv in bubble_versions if bv.bubble_id == bubble.id]
                if len(bubble_versions_list) > 1:
                    bubble_versions_list.sort(key=lambda x: x.created_at)
                    first = datetime.fromisoformat(bubble_versions_list[0].created_at.replace('Z', '+00:00'))
                    last = datetime.fromisoformat(bubble_versions_list[-1].created_at.replace('Z', '+00:00'))
                    lifetime = (last - first).total_seconds()
                    bubble_lifetimes.append(lifetime)
            
            avg_lifetime = sum(bubble_lifetimes) / len(bubble_lifetimes) if bubble_lifetimes else 0.0
            
            stability = MetricsCalculator._calculate_bubble_stability(state)
            coherence = MetricsCalculator._calculate_temporal_coherence(state)
            
            return TemporalMetrics(
                bubble_creation_rate=creation_rate,
                avg_bubble_lifetime=avg_lifetime,
                bubble_stability=stability,
                temporal_coherence=coherence
            )
        except Exception:
            return TemporalMetrics(0.0, 0.0, 0.0, 0.0)
    
    @staticmethod
    def _calculate_bubble_stability(state: PostState) -> float:
        """Calculate how stable bubbles are (fewer changes = more stable)."""
        bubbles = state.bubbles
        bubble_versions = state.bubble_versions
        
        if not bubbles:
            return 1.0
        
        versions_per_bubble = {}
        for bv in bubble_versions:
            versions_per_bubble[bv.bubble_id] = versions_per_bubble.get(bv.bubble_id, 0) + 1
        
        avg_versions = sum(versions_per_bubble.values()) / len(versions_per_bubble) if versions_per_bubble else 1.0
        stability = 1.0 / avg_versions
        
        return min(1.0, stability)
    
    @staticmethod
    def _calculate_temporal_coherence(state: PostState) -> float:
        """Calculate how well comments in bubbles are temporally coherent."""
        comments = {c.id: c for c in state.comments}
        bubble_versions = state.bubble_versions
        
        from datetime import datetime
        
        coherence_scores = []
        
        for bv in bubble_versions:
            if len(bv.comment_ids) < 2:
                continue
            
            try:
                comment_times = []
                for cid in bv.comment_ids:
                    if cid in comments:
                        dt = datetime.fromisoformat(comments[cid].created_at.replace('Z', '+00:00'))
                        comment_times.append(dt.timestamp())
                
                if len(comment_times) < 2:
                    continue
                
                time_span = max(comment_times) - min(comment_times)
                avg_time_gap = time_span / (len(comment_times) - 1) if len(comment_times) > 1 else 0.0
                
                coherence = 1.0 / (1.0 + avg_time_gap / 3600.0)
                coherence_scores.append(coherence)
            except Exception:
                continue
        
        return sum(coherence_scores) / len(coherence_scores) if coherence_scores else 0.0
    
    @staticmethod
    def _calculate_system_metrics(processing_times: List[float]) -> SystemMetrics:
        """Calculate system performance metrics."""
        if not processing_times:
            return SystemMetrics(0.0, 0, 0.0)
        
        avg_time = sum(processing_times) / len(processing_times)
        total_calls = len(processing_times)
        avg_response = avg_time
        
        return SystemMetrics(
            avg_processing_time=avg_time,
            total_api_calls=total_calls,
            avg_response_time=avg_response
        )
    
    @staticmethod
    def save_report(report: EvaluationReport, filepath: str) -> None:
        """Save evaluation report to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(asdict(report), f, indent=2)

