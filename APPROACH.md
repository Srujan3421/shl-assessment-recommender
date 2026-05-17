# Approach

## Catalog Grounding

The recommender uses the official SHL assignment catalog JSON:

`https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json`

`scripts/download_catalog.py` downloads it into `app/data/catalog.json`. The loader accepts the catalog's `link` field and converts it internally to the API `url` field. Optional fields such as description, job levels, languages, duration, keys, remote, and adaptive are normalized safely when present.

Recommendations are created only from loaded catalog records, so the service never fabricates names or URLs.

## Retrieval And Ranking

The `/chat` endpoint is stateless. It reconstructs intent from the full message history on each request, extracting role, seniority, explicit skills, requested assessment type, refinements, exclusions, and comparison intent.

Retrieval uses catalog metadata: name, description, keys, job levels, languages, duration, and type codes. Ranking combines keyword and phrase matching with assessment-type boosting:

- technical, knowledge, and skill requests boost `K`
- aptitude, cognitive, and ability requests boost `A`
- personality and behavior requests boost `P`
- simulations boost `S`
- competency and situational judgment requests boost `C` and `B`

Exact skill matches in assessment names receive the strongest boost. A diversification pass ensures that a Java/Spring/SQL/AWS/Docker query returns those requested areas near the top instead of letting one family of tests crowd out the rest.

## Dialogue Policy

Vague prompts such as "I need an assessment" ask one clarifying question and return an empty recommendation list. Refinements such as "actually add personality tests also" reuse the earlier user context from the supplied message history and update the shortlist.

Comparison requests use alias mapping for common names:

- OPQ, OPQ32, OPQ32r -> Occupational Personality Questionnaire OPQ32r
- GSA -> Global Skills Assessment
- Verify G+ -> SHL Verify Interactive G+

Comparison responses cite only catalog fields available locally.

## Guardrails

The agent refuses salary, compensation, legal hiring, firing, general HR policy, non-SHL recommendations, prompt injection, hidden-prompt requests, and unrelated questions. Refusals and clarifications always return `recommendations: []`.

## Evaluation

Quality is measured with manual probes plus pytest coverage for schema compliance, catalog-only URLs, maximum 10 recommendations, vague-query clarification, refinements, comparison aliases, off-topic refusal, prompt-injection refusal, and public trace-inspired expected names.

What did not work: earlier scraping and detail-page enrichment were inconsistent against the assignment catalog, so the official JSON is now the source of truth. Earlier ranking returned unrelated tests too high for Python and Java stack queries, so exact skill-name boosts, type penalties, and skill diversification were added.
