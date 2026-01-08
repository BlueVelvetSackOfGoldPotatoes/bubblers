#!/usr/bin/env python3
"""
Parallel version of Reddit thread import script.
Pre-embeds comments in batches, then processes clustering sequentially.
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List

import requests

from app.pipeline.embedding import EmbeddingProviderConfig, GPTEmbeddingProvider
from app.reddit_parser import RedditParser


def import_reddit_thread_parallel(file_path: str, api_base: str = "http://127.0.0.1:8000", batch_size: int = 10):
    """
    Import Reddit thread with parallel embedding generation.
    
    Args:
        file_path: Path to Reddit thread text file
        api_base: Base URL for API
        batch_size: Number of comments to embed in each batch
    """
    parser = RedditParser()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    post, comments = parser.parse(text)
    
    print(f"Parsed post: {post.title}")
    print(f"Comments: {len(comments)}")
    
    response = requests.post(
        f"{api_base}/api/posts",
        json={
            "title": post.title,
            "body": post.body,
            "created_at": post.created_at
        }
    )
    
    if not response.ok:
        print(f"Error creating post: {response.status_code} - {response.text}")
        return None
    
    state = response.json()
    post_id = state['post']['id']
    print(f"Created post: {post_id}")
    
    print(f"\nStep 1: Pre-embedding {len(comments)} comments in batches of {batch_size}...")
    embedder = GPTEmbeddingProvider(EmbeddingProviderConfig())
    
    start_time = time.time()
    embedded_comments = []
    
    for i in range(0, len(comments), batch_size):
        batch = comments[i:i+batch_size]
        batch_texts = [c.text for c in batch]
        
        try:
            embeddings = embedder.embed_batch(batch_texts)
            for comment, embedding in zip(batch, embeddings):
                embedded_comments.append((comment, embedding))
            print(f"  Embedded batch {i//batch_size + 1}/{(len(comments)-1)//batch_size + 1}: {len(batch)} comments")
        except Exception as e:
            print(f"  Error embedding batch {i//batch_size + 1}: {e}")
            for comment in batch:
                try:
                    embedding = embedder.embed(comment.text)
                    embedded_comments.append((comment, embedding))
                except Exception as e2:
                    print(f"    Failed to embed comment: {e2}")
    
    embed_time = time.time() - start_time
    print(f"✓ Pre-embedding complete in {embed_time:.2f}s ({len(embedded_comments)}/{len(comments)} comments)")
    
    print(f"\nStep 2: Processing comments through pipeline (clustering + labeling)...")
    print("Note: Processing sequentially to maintain clustering state consistency")
    process_start = time.time()
    created_count = 0
    
    for i, (comment, embedding) in enumerate(embedded_comments):
        payload = {
            "author": {
                "id": comment.author.id,
                "display_name": comment.author.display_name
            },
            "text": comment.text,
            "reply_to_comment_id": comment.reply_to_comment_id,
            "created_at": comment.created_at,
            "embedding": {
                "vector": embedding.vector,
                "dim": embedding.dim,
                "model": embedding.model,
                "hash": embedding.hash
            }
        }
        
        resp = requests.post(
            f"{api_base}/api/posts/{post_id}/comments",
            json=payload,
            timeout=120
        )
        
        if resp.ok:
            created_count += 1
            state = resp.json()
        else:
            print(f"  Error: {resp.status_code} - {resp.text}")
        
        if (i + 1) % 5 == 0 or (i + 1) == len(embedded_comments):
            elapsed = time.time() - process_start
            rate = (i + 1) / elapsed if elapsed > 0 else 0
            print(f"  Progress: {i+1}/{len(embedded_comments)} comments ({rate:.1f} comments/sec)")
    
    total_time = time.time() - start_time
    process_time = time.time() - process_start
    
    print(f"\n✓ Import complete!")
    print(f"  Successfully imported: {created_count}/{len(comments)} comments")
    print(f"  Embedding time: {embed_time:.2f}s")
    print(f"  Processing time: {process_time:.2f}s")
    print(f"  Total time: {total_time:.2f}s")
    print(f"  Throughput: {len(comments)/total_time:.2f} comments/sec")
    print(f"\nView at: {api_base}/")
    
    return state


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "tests.txt"
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    import_reddit_thread_parallel(file_path, batch_size=batch_size)
