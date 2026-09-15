# Duplicate Complaint Detection System - Quick Start Guide

## What's New?

Your complaint system now prevents duplicate complaints by:
1. **Detecting** similar complaints when users submit
2. **Suggesting** upvoting or commenting on existing complaints instead
3. **Allowing** users to add supporting comments without creating duplicates

## Step-by-Step Usage

### Scenario 1: First Complaint (No Duplicates)
```
1. Student submits:
   Title: "Broken electrical outlet in room 201"
   Category: "Electrical"
   Description: "The outlet is exposed and dangerous..."

2. System checks for similar complaints
3. No matches found
4. ✅ Complaint created normally
5. Student redirected to view complaint
```

### Scenario 2: Duplicate Complaint (Similar Exists)
```
1. Student submits:
   Title: "Electrical wiring broken room 201"
   Category: "Electrical"
   Description: "The wiring in room 201 is exposed..."

2. System finds similar complaint:
   - "Broken electrical outlet in room 201"
   - Similarity: 82%
   - Status: Pending
   - Upvotes: 3

3. ⚠️ "Similar Complaints Found" page shows
4. Student chooses from 3 options...
```

### Option 1: View and Upvote Existing
```
Student clicks "View Complaint →"

They see:
- Full complaint details
- Current upvote count: 3 ⬆️
- "👍 Upvote This Complaint" button

Action:
- Click upvote button
- Count increases: 3 → 4
- Their support is recorded
- Complaint priority may increase

Result: Problem gets more attention without duplication
```

### Option 2: Add Supporting Comment
```
Student goes to existing complaint

They scroll to "Supporting Comments" section

They add comment:
"I have the same issue in room 202. 
The outlets there are also exposed. 
This is a serious safety hazard!"

Check "Post anonymously" if desired

Click "💬 Post Comment"

Result: Comment appears immediately in the list
```

Comment Display:
```
┌─────────────────────────────────────┐
│ Supporting Comments                 │
├─────────────────────────────────────┤
│ jane_doe                 Today 2:30pm│
│                                     │
│ I have the same issue in room 202.  │
│ The outlets there are also exposed. │
│ This is a serious safety hazard!    │
│                                     │
│ [Anonymous]              Today 1:15pm│
│                                     │
│ Same problem here. Very dangerous.  │
│                                     │
│ 2 supporting comments               │
└─────────────────────────────────────┘
```

### Option 3: Create New Anyway
```
If student believes their complaint is significantly different:

They can click:
"➕ Create New Complaint Anyway"

Note: This is logged for admin review
Only use if truly a different issue
```

## Benefits of the System

### For Students
- ✅ Don't waste time creating duplicate complaints
- ✅ See existing issues and add your support
- ✅ Voice concerns without re-filing
- ✅ Know you're not alone with the problem

### For Admins
- ✅ Fewer duplicate complaints to process
- ✅ Consolidated information about issues
- ✅ Better priority indicators (upvotes + comments)
- ✅ More accurate problem severity assessment

### For Campus Management
- ✅ Get the real scope of problems
- ✅ Allocate resources better (real issue count)
- ✅ Prioritize based on support, not duplicates
- ✅ Track problem trends more accurately

## Examples

### Example 1: Electrical Issues
```
COMPLAINT A (Created first):
Title: "Electrical outlet not working in room 201"
Created by: Student A
Upvotes: 0
Comments: 0

ONE WEEK LATER...

Student B tries to submit:
Title: "Room 201 electrical outlet broken"

SYSTEM: "Similar complaint found! (85% match)"

Student B Options:
- Upvote: Count goes 0 → 1 ✅
  Admin now sees: "1 user affected, not just one complaint"
- Comment: "Also broken in my dorm room 203"
  Admin now sees: "Multiple rooms affected - bigger issue!"
- Create anyway: Only if truly different problem

RESULT: Admin recognizes pattern, fixes multiple rooms instead of 
treating it as isolated incidents.
```

### Example 2: Ragging/Sensitive Issue
```
COMPLAINT A (Confidential):
Title: "Ragging incident in hostel"
Category: "Ragging"
Status: "Confidential" 🔒

Student B tries similar complaint:

SYSTEM: Skips duplicate check for confidential
("Ragging" is confidential category)

✅ Creates separate complaint
Creates separate record for Principal
Maintains confidentiality

(Confidential complaints don't show supporting comments)
```

### Example 3: Food Quality
```
COMPLAINT A:
"Food in mess is cold and stale"
Upvotes: 5
Comments: 3

COMMENTS:
1. "Same issue. Rice was cold today"
2. "Temperature needs to be monitored"
3. "[Anonymous] Food service needs improvement"

RESULT: Comprehensive view of food quality issues
Admin sees: Not just one person complaining, 
but a systemic issue with supporting evidence
```

## Common Questions

### Q: What if my problem is different from the similar one shown?
**A:** Click "➕ Create New Complaint Anyway" button. The system will create your complaint. Your feedback helps identify whether it's truly a different issue.

### Q: Can I comment anonymously?
**A:** Yes! Check the "Post anonymously" checkbox before posting. Your name won't appear, but staff can still see the comment.

### Q: What happens to my name if I upvote?
**A:** Your name appears in the "Upvoters" list (staff can see it). If you prefer anonymity, add a comment instead with the anonymous option.

### Q: Can I comment on confidential complaints?
**A:** No, confidential complaints (Ragging, Drug Abuse) don't have public comments to maintain privacy. Those go directly to Principal.

### Q: How similar does it need to be to trigger the warning?
**A:** Default is 40% similarity. The system looks at keywords, text content, and overall meaning. Minor wording differences (like "broken" vs "damaged") typically still match.

### Q: Can I delete my comment?
**A:** Currently, comments cannot be deleted. Keep this in mind when posting. If you need urgent removal, contact admin.

### Q: What's the character limit for comments?
**A:** 1,000 characters per comment. The form shows remaining characters as you type.

## Technical Details

### How Similarity is Calculated
```
Score = (Title Match × 30%) + (Description Match × 40%) + (Keywords Match × 30%)

Example:
Title similarity: 70%
Description similarity: 85%
Keywords overlap: 80%

Score = (70 × 0.3) + (85 × 0.4) + (80 × 0.3)
      = 21 + 34 + 24
      = 79%

Result: 79% > 40% threshold → "Similar complaint found!"
```

### Database Changes
- New table: `supporting_comments`
- Stores: who commented, what they said, when, anonymity flag
- Linked to: existing complaints and users
- No impact on existing complaints table

### API Endpoints (For Developers)
```
POST /api/complaints/similar
  Input: {title, description, category}
  Output: [{complaint_data, similarity_score}]

POST /api/complaints/{id}/comment
  Input: {comment, is_anonymous}
  Output: {success, comment_data}

GET /api/complaints/{id}/comments
  Input: complaint_id
  Output: [{comment_data}]
```

## Feedback

### Report Issues
If you find complaints that should have been detected but weren't:
- Note the titles and descriptions
- Contact admin with similarity percentage you expected
- This helps calibrate the system

### Suggest Improvements
- Want lower/higher sensitivity?
- Want to see more/fewer results?
- Want to comment on confidential issues?
- Let admin know your needs!

---

**Ready to use!** Try submitting similar complaints to see the system in action.
