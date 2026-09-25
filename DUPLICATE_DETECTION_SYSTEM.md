# Duplicate Complaint Detection System - Implementation Guide

## Overview
The duplicate complaint detection system has been successfully implemented in your complaint management application. It prevents duplicate submissions by detecting similar complaints before creating new ones, while providing users with options to upvote or add supporting comments instead.

## Features Implemented

### 1. **Similarity Detection Algorithm**
- **Location**: `utils/helpers.py`
- **Functions**:
  - `extract_keywords()`: Removes common English words and extracts meaningful keywords
  - `calculate_similarity()`: Uses Python's `SequenceMatcher` to measure string similarity (0-1 scale)
  - `calculate_keyword_overlap()`: Calculates overlap between keyword sets
  - `find_similar_complaints()`: Combines all metrics with weighted scoring

- **Similarity Score Calculation**:
  - Title similarity: 30% weight
  - Description similarity: 40% weight
  - Keyword overlap: 30% weight
  - Default minimum threshold: 0.4 (40%)

### 2. **New Database Model**
- **Model**: `SupportingComment` in `database.py`
- **Fields**:
  - `id`: Primary key
  - `complaint_id`: Foreign key to complaint
  - `user_id`: Who posted the comment
  - `comment`: Text content (max 1000 chars)
  - `is_anonymous`: Whether posted anonymously
  - `created_at`: Timestamp

### 3. **API Endpoints**

#### Find Similar Complaints
```
POST /api/complaints/similar
Content-Type: application/json

Request Body:
{
  "title": "Broken electrical wiring",
  "description": "The electrical wiring in room 201 is exposed...",
  "category": "Electrical",
  "min_similarity": 0.4
}

Response:
{
  "success": true,
  "similar_complaints": [
    {
      "id": 5,
      "title": "Electrical wiring broken",
      "description": "...",
      "category": "Electrical",
      "status": "Pending",
      "upvote_count": 3,
      "priority": "Medium",
      "created_at": "2024-01-15 10:30:00",
      "similarity_score": 0.82,
      "supporting_comments_count": 2
    }
  ],
  "count": 1
}
```

#### Add Supporting Comment
```
POST /api/complaints/{complaint_id}/comment
Content-Type: application/json

Request Body:
{
  "comment": "I'm experiencing the same issue in room 202",
  "is_anonymous": false
}

Response:
{
  "success": true,
  "message": "Comment added successfully",
  "comment": {
    "id": 1,
    "complaint_id": 5,
    "commenter_name": "john_doe",
    "comment": "I'm experiencing the same issue in room 202",
    "is_anonymous": false,
    "created_at": "2024-01-15 11:45:00"
  }
}
```

#### Get Supporting Comments
```
GET /api/complaints/{complaint_id}/comments

Response:
{
  "success": true,
  "comments": [
    {
      "id": 1,
      "complaint_id": 5,
      "commenter_name": "john_doe",
      "comment": "I'm experiencing the same issue in room 202",
      "is_anonymous": false,
      "created_at": "2024-01-15 11:45:00"
    }
  ],
  "count": 1
}
```

### 4. **User Flow - Submit Complaint**

#### Step 1: Student enters complaint details
- Title and description
- Category selection
- Priority level (optional)
- Anonymity preference

#### Step 2: System checks for duplicates
- Only for non-confidential categories
- Compares against pending and in-progress complaints
- Excludes resolved complaints

#### Step 3: Similar complaints found
If similar complaints detected (similarity ≥ 40%):
- Show up to 5 most similar complaints
- Display:
  - Complaint title
  - Status and upvote count
  - Similarity percentage
  - Category information
  - Preview of description

#### Step 4: Student chooses action
**Option A: View and Upvote**
- Click "View Complaint" link
- Review full complaint details
- Upvote to show support (increases priority)
- View other supporters

**Option B: Add Supporting Comment**
- Click "View Complaint" link
- Scroll to "Supporting Comments" section
- Add your specific experience or additional details
- Option to post anonymously
- Comments visible to all users (non-anonymous only in commenter list)

**Option C: Create New Anyway**
- Click "Create New Complaint Anyway" button
- Complaint is created if still different enough
- Bypass duplicate check is logged

#### Step 5: No duplicates found
- Submit complaint normally
- System creates complaint
- Routes to appropriate admin/principal

## Files Modified

### Backend Files

#### 1. `database.py`
- Added `SupportingComment` model
- Added relationship in `Complaint` model
- `supporting_comments` backref for easy access

#### 2. `utils/helpers.py`
- Added `extract_keywords()` function
- Added `calculate_similarity()` function
- Added `calculate_keyword_overlap()` function
- Added `find_similar_complaints()` function
- Imported `difflib.SequenceMatcher` and `re` modules

#### 3. `routes/complaints.py`
- Updated imports to include `SupportingComment` and `find_similar_complaints`
- Modified `submit_complaint()` route:
  - Added duplicate detection logic
  - Added `skip_duplicate_check` parameter for bypass
  - Returns template with similar complaints if found
- Added `find_similar()` API endpoint
- Added `add_supporting_comment()` API endpoint
- Added `get_supporting_comments()` API endpoint

### Frontend Files

#### 1. `templates/submit_complaint.html`
- Added duplicate warning section with:
  - List of similar complaints with similarity scores
  - Action options (view, upvote, comment, or proceed)
  - Preserved form data when showing duplicates
  - Responsive card layout for similar complaints
  - Color-coded similarity badges

#### 2. `templates/view_complaint.html`
- Added "Supporting Comments" section:
  - Comment form (non-owners only)
  - Character counter (1000 max)
  - Anonymous posting option
  - Comment list with:
    - Commenter name/anonymous indicator
    - Timestamp with "Today", "Yesterday", or date format
    - Comment text
  - Comments count summary
- Added CSS styling for comments
- Added JavaScript functions:
  - `loadComments()`: Fetches comments via API
  - `submitComment()`: Posts new comments
  - `updateCharCount()`: Updates character counter
  - `formatDate()`: Formats timestamps
  - `escapeHtml()`: Prevents XSS

## Testing Recommendations

### 1. Test Similarity Detection
```python
# Example test case
text1 = "Broken electrical wiring in hostel room 201"
text2 = "Electrical wiring is broken in hostel room number 201"
# Expected: ~75-85% similarity (should match)

text1 = "Broken electrical wiring in hostel"
text3 = "Food quality in cafeteria is poor"
# Expected: <40% similarity (should NOT match)
```

### 2. Test User Flows
1. **Create duplicate complaint**:
   - Submit complaint A
   - Submit complaint B with similar content
   - Verify: Similar complaints shown
   - Verify: Options presented correctly

2. **Add supporting comment**:
   - Go to existing complaint
   - Add comment as different user
   - Verify: Comment appears immediately
   - Verify: Anonymous option works

3. **Bypass duplicate check**:
   - Submit complaint with duplicates
   - Click "Create anyway" button
   - Verify: Complaint created despite similarity

### 3. Edge Cases
- Empty or whitespace-only comments
- Very long descriptions (>5000 chars)
- Comments on confidential complaints (should be blocked)
- Upvoting and commenting on same complaint
- Anonymous comments mixed with named ones

## Configuration

### Adjustable Parameters in `find_similar_complaints()`
```python
# Modify min_similarity threshold (0-1 scale)
min_similarity=0.4  # Current: 40% match required

# Modify result limit
limit=5  # Current: Show up to 5 similar complaints

# Modify weights in scoring
title_similarity * 0.3        # 30% weight
desc_similarity * 0.4         # 40% weight
keyword_overlap * 0.3         # 30% weight
```

## Database Schema

### SupportingComment Table
```sql
CREATE TABLE supporting_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    comment TEXT NOT NULL,
    is_anonymous BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

## Performance Considerations

1. **Similarity Checking**: Only done during complaint submission, not on every page load
2. **Database Queries**: Limited to non-confidential, non-resolved complaints in same category
3. **Keyword Extraction**: Lightweight regex-based operation
4. **API Calls**: Comments loaded asynchronously after page load

## Security

1. **Access Control**:
   - Can only comment on non-confidential complaints
   - Cannot comment on own complaint
   - Anonymous option available for all comments

2. **Input Validation**:
   - Comments limited to 1000 characters
   - XSS prevention with `escapeHtml()` function
   - SQL injection prevention via SQLAlchemy ORM

3. **Audit Logging**:
   - Comment additions logged in `audit_logs` table
   - Action: `added_supporting_comment`
   - Includes complaint ID and details

## Future Enhancements

1. **Machine Learning-Based Matching**:
   - Use TF-IDF for better similarity
   - Implement NLP for semantic similarity

2. **Category-Specific Thresholds**:
   - Different sensitivity for different complaint types

3. **Comment Threading**:
   - Replies to specific comments

4. **Upvote Notifications**:
   - Notify original complainant of supporting comments

5. **Bulk Merging**:
   - Admin ability to merge duplicate complaints

## Troubleshooting

### Similar complaints not showing
- Check category is not in `CONFIDENTIAL_CATEGORIES`
- Verify similarity threshold (try lowering `min_similarity`)
- Check database has existing complaints in same category
- Ensure complaints are not in "Resolved" status

### Comments not saving
- Check user is not complaint owner
- Verify complaint is not confidential
- Check comment is not empty and within 1000 chars
- Review browser console for JavaScript errors

### Database errors
- Run `db.create_all()` to create missing tables
- Check for database file corruption
- Verify SQLAlchemy relationships are correct

## Feedback & Support

For issues or suggestions:
1. Check browser console for JavaScript errors
2. Review server logs for Python errors
3. Verify database integrity
4. Test with fresh complaint data
