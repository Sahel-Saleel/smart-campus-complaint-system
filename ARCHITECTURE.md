# System Architecture - Visual Guide

## System Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   COMPLAINT SUBMISSION                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
                  Fill Complaint Form
                  (Title + Description)
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               DUPLICATE DETECTION ENGINE                    │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 1. Extract Keywords & Analyze Text                      ││
│  │ 2. Search Existing Complaints (Same Category)           ││
│  │ 3. Calculate Similarity Scores                          ││
│  │ 4. Return Top 5 Matches (if score ≥ 40%)               ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            ↓
                    ┌──────────────┐
                    │  Match Found?│
                    └──────────────┘
                     /            \
                   YES             NO
                    /               \
                   ↓                 ↓
        ┌────────────────────┐  ┌──────────────────┐
        │  Show Duplicates   │  │ Create Complaint │
        │  Page w/ Options   │  │     Normally     │
        └────────────────────┘  └──────────────────┘
         /          |          \
        ↓           ↓           ↓
    ┌────────┐ ┌─────────┐ ┌──────────┐
    │ Upvote │ │ Comment │ │ Create   │
    │        │ │         │ │ Anyway   │
    └────────┘ └─────────┘ └──────────┘
```

## Data Model Relationships

```
Users
  ├── Complaints (created by user)
  ├── Upvotes (user upvotes complaints)
  ├── SupportingComments (user adds comments)
  └── AuditLogs (user actions logged)

Complaints
  ├── Upvotes (complaint receives upvotes)
  ├── SupportingComments (users comment on complaint)
  ├── Notifications (about this complaint)
  └── AuditLogs (actions on this complaint)

SupportingComments (NEW)
  ├── Complaint (which complaint)
  └── User (who commented)
```

## Similarity Scoring Formula

```
Similarity Score = (Title Match × 30%) 
                 + (Description Match × 40%) 
                 + (Keyword Overlap × 30%)

Result Ranges:
  0-0.4    = No match (not shown)
  0.4-0.6  = Weak match
  0.6-0.8  = Good match
  0.8-1.0  = Strong match
```

## Keyword Extraction Example

```
Original Text:
"The electrical wiring in hostel room 201 is broken"

Step 1: Lowercase & split
['the', 'electrical', 'wiring', 'in', 'hostel', 'room', '201', 'is', 'broken']

Step 2: Remove stop words
['electrical', 'wiring', 'hostel', 'room', '201', 'broken']

Step 3: Remove short words (< 3 chars)
['electrical', 'wiring', 'hostel', 'room', 'broken']

Final Keywords: {electrical, wiring, hostel, room, broken}
```

## Comment System Flow

```
User Visits Complaint
         ↓
Is user the creator? 
    ├─ YES → Hide comment form
    └─ NO  ↓
Is complaint confidential?
    ├─ YES → Hide comment form
    └─ NO  ↓
Show Comment Form
         ↓
User enters comment & clicks submit
         ↓
┌─────────────────────────────────────┐
│ API: POST /complaints/{id}/comment  │
├─────────────────────────────────────┤
│ Validate:                           │
│  - Not owner ✓                      │
│  - Not confidential ✓               │
│  - Not empty ✓                      │
│  - ≤ 1000 chars ✓                   │
│  - User authenticated ✓             │
└─────────────────────────────────────┘
         ↓
Save to Database
         ↓
Log Audit Entry
         ↓
Return Success
         ↓
Refresh Comments List (JavaScript)
```

## File Organization

```
Project Root/
├── Backend/
│   ├── app.py (entry point)
│   ├── database.py ✏️ (models - modified)
│   ├── utils/
│   │   ├── helpers.py ✏️ (functions - modified)
│   │   ├── decorators.py
│   │   └── __init__.py
│   └── routes/
│       ├── complaints.py ✏️ (endpoints - modified)
│       ├── admin.py
│       ├── auth.py
│       └── ...
│
├── Frontend/
│   ├── templates/
│   │   ├── submit_complaint.html ✏️ (modified)
│   │   ├── view_complaint.html ✏️ (modified)
│   │   ├── base.html
│   │   └── ...
│   └── static/
│       ├── css/
│       ├── js/
│       └── ...
│
├── Database/
│   └── complaint_system.db (SQLite)
│
└── Documentation/
    ├── IMPLEMENTATION_SUMMARY.md ✨ (new)
    ├── DUPLICATE_DETECTION_SYSTEM.md ✨ (new)
    ├── USER_GUIDE.md ✨ (new)
    ├── CHANGES.md ✨ (new)
    └── IMPLEMENTATION_CHECKLIST.md ✨ (new)

Legend: ✏️ = Modified, ✨ = New
```

## API Endpoints

```
┌────────────────────────────────────────────────────────────┐
│ FIND SIMILAR COMPLAINTS                                    │
├────────────────────────────────────────────────────────────┤
│ POST /api/complaints/similar                               │
│ 
│ Request:
│ {
│   "title": "Broken electrical wiring",
│   "description": "The wiring in room 201...",
│   "category": "Electrical",
│   "min_similarity": 0.4
│ }
│
│ Response:
│ {
│   "success": true,
│   "similar_complaints": [
│     {
│       "id": 5,
│       "title": "Electrical outlet broken",
│       "similarity_score": 0.82,
│       "upvote_count": 3,
│       "status": "Pending"
│     }
│   ],
│   "count": 1
│ }
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ ADD SUPPORTING COMMENT                                     │
├────────────────────────────────────────────────────────────┤
│ POST /api/complaints/{id}/comment                          │
│
│ Request:
│ {
│   "comment": "I'm experiencing the same issue...",
│   "is_anonymous": false
│ }
│
│ Response:
│ {
│   "success": true,
│   "message": "Comment added successfully",
│   "comment": {
│     "id": 1,
│     "commenter_name": "john_doe",
│     "created_at": "2024-01-15 11:45:00"
│   }
│ }
└────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────┐
│ GET SUPPORTING COMMENTS                                    │
├────────────────────────────────────────────────────────────┤
│ GET /api/complaints/{id}/comments                          │
│
│ Response:
│ {
│   "success": true,
│   "comments": [
│     {
│       "id": 1,
│       "commenter_name": "john_doe",
│       "comment": "I'm experiencing...",
│       "is_anonymous": false,
│       "created_at": "2024-01-15 11:45:00"
│     }
│   ],
│   "count": 1
│ }
└────────────────────────────────────────────────────────────┘
```

## Security Layers

```
┌─────────────────────────────────────────────────────────┐
│               INPUT VALIDATION                          │
├─────────────────────────────────────────────────────────┤
│ • Comment length ≤ 1000 chars                           │
│ • Category validation against CATEGORY_ROUTING          │
│ • Title/description length checks                       │
│ • Empty content rejection                               │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              ACCESS CONTROL                             │
├─────────────────────────────────────────────────────────┤
│ • User authentication (login_required)                  │
│ • User ID validation on backend                         │
│ • Can't comment on own complaint                        │
│ • Can't comment on confidential                         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              OUTPUT ENCODING                            │
├─────────────────────────────────────────────────────────┤
│ • HTML escaping in JavaScript                           │
│ • Safe DOM manipulation                                 │
│ • No innerHTML with user content                        │
│ • Template auto-escaping                                │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│              AUDIT LOGGING                              │
├─────────────────────────────────────────────────────────┤
│ • All comment additions logged                          │
│ • User ID recorded                                      │
│ • Complaint ID recorded                                 │
│ • Timestamp recorded                                    │
│ • Action type: added_supporting_comment                │
└─────────────────────────────────────────────────────────┘
```

## Implementation Timeline

```
Phase 1: Core System (✅ COMPLETE)
├── Database model created
├── Similarity functions implemented
├── API endpoints created
└── Basic testing passed

Phase 2: UI Integration (✅ COMPLETE)
├── Duplicate detection UI added
├── Comment form added
├── Comment display added
└── Styling completed

Phase 3: Documentation (✅ COMPLETE)
├── Technical docs written
├── User guide created
├── API docs documented
└── Deployment guide created

Phase 4: Testing & Verification (✅ COMPLETE)
├── Syntax validation passed
├── Algorithm testing passed
├── Database integration verified
└── System ready for deployment
```

## Performance Metrics

```
Operation                    Time Complexity   Space Complexity
─────────────────────────────────────────────────────────────
Extract keywords            O(n)              O(k)
Calculate similarity         O(n)              O(1)
Keyword overlap             O(k₁ + k₂)        O(k)
Find similar complaints     O(m × n)          O(m)
Add comment                 O(1)              O(1)
Load comments               O(c)              O(c)
─────────────────────────────────────────────────────────────

Where:
n = text length
m = number of complaints to check
k = number of unique keywords
c = number of comments
```

## Decision Points in Code

```
User submits complaint
    ↓
Valid input?
    ├─ NO → Error message → Exit
    └─ YES ↓
Category in CONFIDENTIAL_CATEGORIES?
    ├─ YES → Skip duplicate check → Create
    └─ NO ↓
Call find_similar_complaints()
    ↓
Similar found (≥0.4)?
    ├─ NO → Create complaint
    └─ YES ↓
User clicks "Create Anyway"?
    ├─ NO → User chooses upvote/comment
    └─ YES ↓
Create complaint with skip flag
    ↓
Log audit entry
    ↓
Complete
```

---

**Visual Guide Complete** ✅
