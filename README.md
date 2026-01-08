# Comment Bubbles MVP

A FastAPI application that demonstrates real-time comment clustering and visualization. Comments are automatically embedded, clustered into semantic "bubbles," labeled with AI-generated summaries, and classified by sentiment (agree/disagree/pass).

## Features

- **Real-time clustering**: Comments are automatically grouped into semantic bubbles as they arrive
- **GPT-powered**: Uses OpenAI embeddings (`text-embedding-3-small`) and GPT-4o-mini for labeling and sentiment classification
- **Temporal visualization**: Interactive timeline showing bubble evolution over time
- **Voting classification**: Each comment is classified as "agree", "disagree", or "pass" relative to the post
- **Multi-post support**: Manage multiple conversations with easy switching
- **Reddit import**: Import Reddit threads from text files
- **Comprehensive evaluation**: Detailed analysis of clustering decisions and recommendations
- **Parallel processing**: Batch embedding generation for faster imports

## Requirements

- Python 3.11+
- OpenAI API key (set in `.env` file as `GPT_KEY`)

## Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -U pip
pip install -r requirements.txt

# Create .env file with your OpenAI API key
echo "GPT_KEY=your-api-key-here" > .env

# Run the server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000 in your browser.

## API Endpoints

### Posts
- `GET /api/posts/list` - List all available posts
- `POST /api/posts` - Create a new post
  ```json
  {
    "title": "Post title",
    "body": "Post body text",
    "created_at": "2024-01-01T00:00:00Z"  // optional
  }
  ```
- `GET /api/posts/{post_id}/state` - Get full state for a post
- `POST /api/posts/{post_id}/load` - Load a post as current
- `GET /api/current-state` - Get current post state
- `GET /api/posts/{post_id}/evaluate` - Get detailed evaluation report

### Comments
- `POST /api/posts/{post_id}/comments` - Add a comment
  ```json
  {
    "author": {
      "id": "user-id",
      "display_name": "Display Name"
    },
    "text": "Comment text",
    "reply_to_comment_id": "uuid-or-null",
    "created_at": "2024-01-01T00:00:00Z",  // optional
    "embedding": {  // optional, for pre-computed embeddings
      "vector": [...],
      "dim": 1536,
      "model": "text-embedding-3-small",
      "hash": "..."
    }
  }
  ```

## Data Model

### Comment
```json
{
  "id": "uuid",
  "post_id": "uuid",
  "created_at": "iso-8601",
  "author": { "id": "string", "display_name": "string" },
  "text": "string",
  "reply_to_comment_id": "uuid|null",
  "embedding": {
    "vector": [0.1, 0.2, ...],
    "dim": 1536,
    "model": "text-embedding-3-small",
    "hash": "sha256-hex"
  },
  "assigned_bubble_id": "uuid|null",
  "assigned_bubble_version_id": "uuid|null",
  "vote": "agree|disagree|pass|null"
}
```

### BubbleVersion
```json
{
  "id": "uuid",
  "bubble_id": "uuid",
  "post_id": "uuid",
  "created_at": "iso-8601",
  "window": { "start_at": "iso-8601", "end_at": "iso-8601" },
  "label": "string",
  "essence": "string",
  "confidence": 0.0-1.0,
  "comment_ids": ["uuid"],
  "representative_comment_ids": ["uuid"],
  "centroid_embedding": { ... }
}
```

## Pipeline Architecture

### 1. Embedding Provider (`app/pipeline/embedding.py`)
- **Implementation**: `GPTEmbeddingProvider` using OpenAI `text-embedding-3-small`
- **Dimension**: 1536
- **Features**: Batch embedding support for parallel processing
- **Caching**: Embeddings are hashed for consistency

### 2. Clusterer (`app/pipeline/clusterer.py`)
- **Algorithm**: Online incremental clustering
- **Threshold**: 0.58 (cosine similarity)
- **Behavior**: Assigns comments to existing bubbles or creates new ones
- **Centroid**: Recalculated for each bubble version

### 3. Labeler (`app/pipeline/labeler.py`)
- **Implementation**: `GPTLabeler` using GPT-4o-mini
- **Output**: Label (2-4 words), essence (1-2 sentences), confidence score
- **Representatives**: Selects 3-5 representative comments per bubble

### 4. Voter (`app/pipeline/voter.py`)
- **Implementation**: `GPTVoter` using GPT-4o-mini
- **Classification**: "agree", "disagree", or "pass" relative to the post
- **Purpose**: Sentiment analysis for understanding comment stance

## Evaluation System

The system includes comprehensive evaluation tools to analyze clustering quality:

### Evaluation Script
```bash
python evaluate_system.py <post_id> [threshold]
```

### Evaluation Features
- **Clustering Decisions**: Analysis of each assignment decision with similarity scores
- **Bubble Analysis**: Cohesion, similarity ranges, potential merges/splits
- **Threshold Analysis**: Optimal threshold recommendations
- **Recommendations**: Actionable suggestions for improvement
- **Voting Analysis**: Distribution of agree/disagree/pass across bubbles

### Metrics Calculated
- Clustering: Silhouette score, cohesion, separation, entropy
- Labeling: Uniqueness, coverage, confidence
- Temporal: Creation rate, stability, coherence
- System: Processing time, API calls

## Reddit Import

Import Reddit threads from text files:

```bash
# Sequential import
python test_reddit_import.py tests.txt

# Parallel import (faster, pre-embeds in batches)
python test_reddit_import_parallel.py tests.txt [batch_size]
```

The parser extracts:
- Post title and body
- Comments with authors and timestamps
- Reply relationships
- Relative time parsing ("1y ago", "10mo ago", etc.)

## UI Features

### Timeline Visualization
- **Lane-based layout**: Bubbles arranged in stable lanes
- **Temporal positioning**: X-axis represents time progression
- **Size encoding**: Bubble size reflects comment count
- **Vote summaries**: Shows agree/disagree/pass counts on each bubble
- **Confidence indicators**: Color-coded confidence scores

### Bubble Inspector
- Label and essence display
- Vote distribution breakdown
- Representative comments
- Full comment list with voting badges
- Metadata (confidence, window, bubble ID)

### Comment Feed
- Chronological display
- Vote badges (color-coded: green=agree, red=disagree, gray=pass)
- Bubble assignment indicators
- Author and timestamp information

## Configuration

### Pipeline Config (`app/pipeline/orchestrator.py`)
- `assign_threshold`: 0.58 (cosine similarity threshold)
- `embedding_model`: "text-embedding-3-small"
- `embedding_dim`: 1536
- `labeler_mode`: "live" (GPT-based)

### Environment Variables
- `GPT_KEY`: OpenAI API key (required)

## Testing

### Run Tests
```bash
python run_tests.py
```

This will:
1. Import a Reddit thread
2. Calculate metrics
3. Generate evaluation reports
4. Capture screenshots

### Manual Testing
1. Create a post via UI or API
2. Add comments (manually or via import)
3. Observe bubble formation in timeline
4. Click bubbles to inspect details
5. Use evaluation endpoint to analyze quality

## Project Structure

```
bubblers/
├── app/
│   ├── main.py              # FastAPI application
│   ├── models.py            # Data models
│   ├── store.py             # In-memory data store
│   ├── utils.py             # Utility functions
│   ├── metrics.py           # Metrics calculation
│   ├── evaluation.py         # Detailed evaluation system
│   ├── reddit_parser.py      # Reddit thread parser
│   ├── pipeline/
│   │   ├── orchestrator.py  # Main pipeline coordinator
│   │   ├── embedding.py      # GPT embedding provider
│   │   ├── clusterer.py     # Online clustering
│   │   ├── labeler.py       # GPT labeler
│   │   └── voter.py          # Sentiment classifier
│   └── static/
│       ├── index.html        # Frontend HTML
│       ├── app.js            # Frontend JavaScript
│       └── styles.css        # Styling
├── evaluate_system.py        # Evaluation CLI tool
├── test_reddit_import.py     # Sequential Reddit import
├── test_reddit_import_parallel.py  # Parallel Reddit import
├── run_tests.py              # Test runner
└── requirements.txt          # Dependencies
```

## Key Design Decisions

### Online Clustering
- Incremental algorithm processes comments one at a time
- Maintains state across comment additions
- Creates new bubbles when similarity is below threshold

### Temporal Versioning
- Each bubble update creates a new `BubbleVersion`
- Preserves history through `BubbleEdge` relationships
- Enables visualization of bubble evolution

### Provenance
- Every bubble shows representative comments
- Full comment list always accessible
- Evaluation system provides transparency into decisions

### Voting Classification
- Automatic sentiment analysis relative to post
- Enables understanding of agreement/disagreement patterns
- Visual indicators in UI for quick scanning

## Limitations

- **In-memory storage**: Data is lost on server restart
- **Single-threaded processing**: Comments processed sequentially (clustering requires state)
- **No persistence**: No database backend (MVP scope)
- **No authentication**: All operations are open
- **Rate limiting**: Subject to OpenAI API rate limits

## Future Enhancements

- Database persistence
- Real-time updates via WebSocket
- User corrections for bubble labels
- Split/merge detection algorithms
- Advanced visualization (2D layout, force-directed graphs)
- Multi-language support
- Export/import functionality

## License

See project files for license information.
