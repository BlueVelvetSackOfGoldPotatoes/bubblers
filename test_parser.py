#!/usr/bin/env python3
from app.reddit_parser import RedditParser

p = RedditParser()
with open('tests.txt') as f:
    post, comments = p.parse(f.read())

print(f'Post: {post.title[:60]}...')
print(f'Body length: {len(post.body)} chars')
print(f'Comments: {len(comments)}')
print('\nFirst 5 comments:')
for i, c in enumerate(comments[:5]):
    print(f'  {i+1}. {c.author.display_name}: {c.text[:60]}...')

