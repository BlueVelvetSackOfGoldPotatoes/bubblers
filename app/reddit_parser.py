from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.models import Author


@dataclass
class RedditPost:
    title: str
    body: str
    created_at: str


@dataclass
class RedditComment:
    author: Author
    text: str
    created_at: str
    reply_to_comment_id: Optional[str] = None
    end_line: int = 0


class RedditParser:
    """
    Parser for Reddit thread copy-paste text format.
    
    Parses Reddit threads from plain text format and converts them
    to Post and Comment objects for the application.
    """
    
    def __init__(self) -> None:
        self._base_date = datetime.now(timezone.utc)
    
    def parse(self, text: str, base_date: Optional[datetime] = None) -> tuple[RedditPost, List[RedditComment]]:
        """
        Parse Reddit thread text into post and comments.
        
        Args:
            text: Raw Reddit thread text
            base_date: Base date for relative time calculations (defaults to now)
            
        Returns:
            Tuple of (RedditPost, List[RedditComment])
        """
        if base_date:
            self._base_date = base_date
        
        lines = text.split('\n')
        post = self._parse_post(lines)
        comments = self._parse_comments(lines)
        
        return post, comments
    
    def _parse_post(self, lines: List[str]) -> RedditPost:
        """Extract post title and body from lines."""
        title = ""
        body_lines = []
        in_body = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            if not title:
                if line and not line.startswith('u/') and 'avatar' not in line.lower():
                    title = line
                    in_body = True
                    continue
            
            if in_body:
                if line.startswith('u/') and 'avatar' in line.lower():
                    break
                if line in ['Upvote', 'Downvote', 'Go to comments', 'Share', 'Sort by:', 'Best', 'Search Comments', 'Comments Section']:
                    break
                if line.startswith('Archived post'):
                    break
                body_lines.append(line)
        
        body = '\n\n'.join(body_lines).strip()
        if not body:
            body = title
        
        return RedditPost(
            title=title or "Reddit Post",
            body=body,
            created_at=self._base_date.isoformat().replace('+00:00', 'Z')
        )
    
    def _parse_comments(self, lines: List[str]) -> List[RedditComment]:
        """Extract comments from lines."""
        comments = []
        i = 0
        comment_map = {}
        comment_counter = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('u/') and 'avatar' in line.lower():
                comment_data = self._parse_comment_block(lines, i, comment_map)
                if comment_data:
                    comment_id = f"comment_{comment_counter}"
                    comment_counter += 1
                    comment_map[comment_id] = comment_data
                    comments.append(comment_data)
                    i = comment_data.end_line
                else:
                    i += 1
            else:
                i += 1
        
        return comments
    
    def _parse_comment_block(self, lines: List[str], start: int, comment_map: dict) -> Optional[RedditComment]:
        """Parse a single comment block starting at start index."""
        if start >= len(lines):
            return None
        
        username_line = lines[start]
        username_match = re.search(r'u/([^\s]+)', username_line)
        if not username_match:
            return None
        
        username = username_match.group(1)
        i = start + 1
        
        is_op = False
        time_str = None
        text_lines = []
        in_text = False
        end_line = start
        seen_username = False
        seen_time = False
        
        while i < len(lines):
            line = lines[i].strip()
            
            if not line:
                if in_text:
                    text_lines.append("")
                i += 1
                continue
            
            if line == 'OP':
                is_op = True
                i += 1
                continue
            
            if line == username and not seen_username:
                seen_username = True
                i += 1
                continue
            
            if line == '•':
                i += 1
                continue
            
            if 'ago' in line.lower() and not seen_time:
                time_str = line
                seen_time = True
                in_text = True
                i += 1
                continue
            
            if line.startswith('Edited'):
                i += 1
                continue
            
            if line in ['Upvote', 'Downvote']:
                end_line = i
                break
            
            if line.startswith('u/') and 'avatar' in line.lower():
                end_line = i
                break
            
            if in_text:
                if line not in ['Share', 'Sort by:', 'Best', 'Search Comments', 'Expand comment search', 'Comments Section', 'More replies']:
                    if not (line.isdigit() and i + 1 < len(lines) and lines[i+1].strip() in ['Upvote', 'Downvote']):
                        text_lines.append(line)
            
            i += 1
            end_line = i
        
        text = '\n'.join(text_lines).strip()
        if not text or text in ['[deleted]', 'More replies']:
            return None
        
        created_at = self._parse_relative_time(time_str) if time_str else self._base_date.isoformat().replace('+00:00', 'Z')
        
        display_name = username if not is_op else f"{username} (OP)"
        
        comment = RedditComment(
            author=Author(id=username, display_name=display_name),
            text=text,
            created_at=created_at,
            reply_to_comment_id=None
        )
        comment.end_line = end_line
        return comment
    
    def _parse_relative_time(self, time_str: str) -> str:
        """Convert relative time like '1y ago' to ISO timestamp."""
        if not time_str:
            return self._base_date.isoformat().replace('+00:00', 'Z')
        
        time_str = time_str.lower().strip()
        
        patterns = [
            (r'(\d+)\s*y(?:ear|r)?s?\s*ago', 'years'),
            (r'(\d+)\s*mo(?:nth|n)?s?\s*ago', 'months'),
            (r'(\d+)\s*w(?:eek|k)?s?\s*ago', 'weeks'),
            (r'(\d+)\s*d(?:ay)?s?\s*ago', 'days'),
            (r'(\d+)\s*h(?:our|r)?s?\s*ago', 'hours'),
            (r'(\d+)\s*m(?:inute|in)?s?\s*ago', 'minutes'),
        ]
        
        for pattern, unit in patterns:
            match = re.search(pattern, time_str)
            if match:
                value = int(match.group(1))
                delta = self._create_delta(value, unit)
                result = self._base_date - delta
                return result.isoformat().replace('+00:00', 'Z')
        
        return self._base_date.isoformat().replace('+00:00', 'Z')
    
    def _create_delta(self, value: int, unit: str) -> timedelta:
        """Create timedelta from value and unit."""
        if unit == 'years':
            return timedelta(days=value * 365)
        elif unit == 'months':
            return timedelta(days=value * 30)
        elif unit == 'weeks':
            return timedelta(weeks=value)
        elif unit == 'days':
            return timedelta(days=value)
        elif unit == 'hours':
            return timedelta(hours=value)
        elif unit == 'minutes':
            return timedelta(minutes=value)
        return timedelta()

