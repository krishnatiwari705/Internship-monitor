# Internship Monitor Crawler — Stage 1

This directory contains the configuration for the multi-source internship discovery layer.

## Target profile
- AI / GenAI / RAG / ML internships
- Backend / Python / Java / Node.js internships
- Software Engineer / SDE internships
- Full-stack internships
- Delhi NCR: Delhi, Noida, Gurgaon/Gurugram, Greater Noida, Faridabad, Ghaziabad
- Remote India
- Strong preference for 2027-eligible roles

## Source strategy
The crawler is designed to combine structured ATS sources (Greenhouse/Lever), search/RSS discovery, and later company career-page adapters.

## Next implementation steps
1. Fetch structured Greenhouse and Lever postings.
2. Add source adapters and normalize every posting to one schema.
3. Store stable source IDs and URLs for deduplication.
4. Detect new/updated postings using source timestamps.
5. Add profile/JD matching and freshness scoring.
6. Connect results to the existing dashboard and alert layer.
