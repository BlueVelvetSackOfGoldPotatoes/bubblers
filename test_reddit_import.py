#!/usr/bin/env python3
"""
Script to import Reddit thread from text file and create post/comments via API.
"""

import json
import sys
from pathlib import Path

import requests

from app.reddit_parser import RedditParser


def import_reddit_thread(file_path: str, api_base: str = "http://127.0.0.1:8000"):
    """Import Reddit thread from text file."""
    parser = RedditParser()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    
    post, comments = parser.parse(text)
    
    print(f"Parsed post: {post.title}")
    print(f"Body length: {len(post.body)} chars")
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
    
    created_comments = []
    for i, comment in enumerate(comments):
        print(f"Adding comment {i+1}/{len(comments)}: {comment.author.display_name[:30]}...")
        
        response = requests.post(
            f"{api_base}/api/posts/{post_id}/comments",
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
        
        if response.ok:
            created_comments.append(comment)
            state = response.json()
        else:
            print(f"  Error: {response.status_code} - {response.text}")
    
    print(f"\n✓ Successfully imported {len(created_comments)}/{len(comments)} comments")
    print(f"View at: {api_base}/")
    
    return state


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "tests.txt"
    import_reddit_thread(file_path)

