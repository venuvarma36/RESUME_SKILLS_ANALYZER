# Project Flow and Model Configuration

## 1) Entry points (start of the project)

- CLI entry: `main()` in [main.py](main.py#L90) is the starting function for command‑line usage. It parses args and routes to UI, tests, or matching.
- Matching entry: `match_resumes()` in [main.py](main.py#L25) initializes `ResumeJDMatcher` and triggers the pipeline via `match_resumes_to_jd()`.
- Web UI entry: `--ui` launches Streamlit and runs [ui/app.py](ui/app.py) (called from [main.py](main.py#L138)).

## 2) End‑to‑end flow (input → preprocessing → matching → output)

### 2.1 Input
- Inputs are resume file paths and a job description (file path or raw text). The CLI collects these in [main.py](main.py#L155) and passes them to `match_resumes()`.
- Batch matching is driven by `ResumeJDMatcher.match_resumes_to_jd()` in [matching_engine/matcher.py](matching_engine/matcher.py#L259).

### 2.2 Text extraction (PDF/DOCX + OCR fallback)
- Each resume file is extracted via `TextExtractor.extract()` in [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L40).
- PDF path uses `_extract_from_pdf()` in [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L89), with:
  - PyMuPDF for layout blocks (page text + bounding boxes) [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L161)
  - pdfplumber as primary text extractor [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L199)
  - Optional PyPDF2 fallback if configured [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L221)
  - Optional Camelot table extraction [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L244)
  - OCR fallback with Tesseract + pdf2image [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L259)
- DOCX path uses `_extract_from_docx()` in [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L299).
- The extracted text is returned to `ResumeJDMatcher.process_resume()` in [matching_engine/matcher.py](matching_engine/matcher.py#L47).

### 2.3 Preprocessing (available, but not wired in the matching path)
- `TextPreprocessor.preprocess()` is implemented in [preprocessing/text_preprocessor.py](preprocessing/text_preprocessor.py#L74) and configured in [config/config.yaml](config/config.yaml#L26).
- `ResumeJDMatcher` instantiates `TextPreprocessor` in [matching_engine/matcher.py](matching_engine/matcher.py#L26), but the current matching flow does not call it for resumes or job descriptions. If you want preprocessing in the pipeline, the call should be added before skill extraction.

### 2.4 Skill extraction (hybrid NER + rules + keyword expansion)
- Skill extraction is performed in `SkillExtractor.extract()` in [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L201).
- Models and methods:
  - BERT NER pipeline (`dslim/bert-base-NER` by default) [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L141)
  - Optional DeBERTa token classification model [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L169)
  - Optional spaCy NER model [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L187)
  - Rule‑based dictionary matching [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L323)
  - Keyword expansion via RAKE and KeyBERT [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L407)
  - Canonicalization and ontology filtering (RapidFuzz) [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L434)
- The extractor is used in both `process_resume()` and `process_job_description()` in [matching_engine/matcher.py](matching_engine/matcher.py#L47).

### 2.5 Feature engineering (embeddings + similarity features)
- Embeddings are generated in `FeatureEngineer.generate_weighted_skill_embedding()` in [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L221).
- Similarity features for matching are created in `compute_quadruple_features()` in [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L303):
  - semantic (SentenceTransformer)
  - Jaccard overlap
  - fuzzy token similarity (RapidFuzz)
  - graph‑style heuristic score
  - optional context/domain classifiers (DeBERTa/RoBERTa)
- Fused similarity uses `hybrid_similarity()` in [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L355), which falls back to weighted fusion unless a meta‑learner is configured.

### 2.6 Matching (scoring and ranking)
- `ResumeJDMatcher.compute_match_score()` computes category overlap, embedding similarity, and fused quadruple similarity in [matching_engine/matcher.py](matching_engine/matcher.py#L139).
- `match_resumes_to_jd()` aggregates results into a ranked DataFrame in [matching_engine/matcher.py](matching_engine/matcher.py#L259).

### 2.7 Output
- CLI prints summary and optionally saves CSV/JSON in `match_resumes()` [main.py](main.py#L42).
- The saved output path is determined by CLI arguments in [main.py](main.py#L71).

## 3) Models used and where they are loaded

- SentenceTransformer embeddings
  - Load: `FeatureEngineer._initialize_model()` [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L70)
  - Default model: `sentence-transformers/all-MiniLM-L6-v2` in [config/config.yaml](config/config.yaml#L67)
- ONNX runtime (optional)
  - Load: `FeatureEngineer._initialize_onnx_session()` [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L84)
  - Config: [config/config.yaml](config/config.yaml#L74)
- NER (BERT)
  - Load: `SkillExtractor._initialize_ner_model()` [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L141)
  - Default model: `dslim/bert-base-NER` in [config/config.yaml](config/config.yaml#L38)
- DeBERTa token classification (optional NER)
  - Load: `SkillExtractor._initialize_deberta_model()` [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L169)
  - Default model: `microsoft/deberta-v3-base` in [config/config.yaml](config/config.yaml#L41)
- spaCy NER (optional)
  - Load: `SkillExtractor._initialize_spacy_model()` [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L187)
  - Default model: `en_core_web_trf` in [config/config.yaml](config/config.yaml#L43)
- KeyBERT keyword model (optional)
  - Load: `SkillExtractor._initialize_keybert()` [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L97)
  - Default model: `sentence-transformers/all-MiniLM-L6-v2` in [config/config.yaml](config/config.yaml#L55)
- Context classifier (optional DeBERTa sequence classification)
  - Load: `FeatureEngineer.generate_contextual_signals()` [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L417)
  - Default model: `microsoft/deberta-v3-base` in [config/config.yaml](config/config.yaml#L77)
- Domain relevance classifier (optional RoBERTa)
  - Load: `FeatureEngineer._compute_domain_relevance()` [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L442)
  - Default model: `roberta-base` in [config/config.yaml](config/config.yaml#L77)
- Meta‑learner (optional XGBoost regressor)
  - Load: `FeatureEngineer._initialize_meta_model()` [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L104)
  - Config path: [config/config.yaml](config/config.yaml#L96)
- SHAP explainability (optional)
  - Use: `FeatureEngineer.explain_with_shap()` [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L388)

## 4) Parameter configuration by stage (with file references)

### 4.1 Text extraction parameters
- Config keys in [config/config.yaml](config/config.yaml#L11):
  - `min_text_length`, `ocr_fallback`, `ocr_language`, `pdf_extraction_method`, `use_pymupdf`, `use_camelot`, `capture_layout`, `ocr_min_chars`, `ocr_page_limit`, `poppler_path`, `tesseract_path`
- Runtime usage in `TextExtractor.__init__()` [text_extraction/text_extractor.py](text_extraction/text_extractor.py#L24)

### 4.2 Preprocessing parameters
- Config keys in [config/config.yaml](config/config.yaml#L26):
  - `lowercase`, `remove_punctuation`, `remove_stopwords`, `lemmatize`, `preserve_technical_terms`, `technical_terms_pattern`, `min_token_length`, `max_token_length`
- Runtime usage in `TextPreprocessor.__init__()` [preprocessing/text_preprocessor.py](preprocessing/text_preprocessor.py#L24)

### 4.3 Skill extraction parameters
- Config keys in [config/config.yaml](config/config.yaml#L37):
  - `use_ner_model`, `ner_model_name`, `use_deberta_ner`, `deberta_model_name`, `use_spacy_ner`, `spacy_model`, `use_rule_based`, `use_rake`, `use_keybert`, `keyword_top_n`, `confidence_threshold`, `deduplicate`, `normalize_synonyms`, `canonicalize`, `canonical_match_threshold`, `keyword_embedding_model`
- Runtime usage in `SkillExtractor.__init__()` [skill_extraction/skill_extractor.py](skill_extraction/skill_extractor.py#L51)

### 4.4 Feature engineering parameters
- Config keys in [config/config.yaml](config/config.yaml#L67):
  - `embedding_model`, `embedding_dim`, `cache_embeddings`, `normalize_vectors`, `batch_size`, `use_onnx`, `onnx_model_path`, `enable_contextual_signals`, `roberta_model_name`, `deberta_class_model`, `roberta_domain_model`
- Runtime usage in `FeatureEngineer.__init__()` [feature_engineering/feature_engineer.py](feature_engineering/feature_engineer.py#L32)

### 4.5 Matching parameters
- Config keys in [config/config.yaml](config/config.yaml#L81):
  - `similarity_metric`, `weights.*`, `min_match_threshold`, `fuzzy_weight`, `graph_weight`, `semantic_weight`, `jaccard_weight`, `context_weight`, `domain_weight`, `meta_model_path`, `meta_model_trained`, `shap_enabled`, `domain_adaptive_weights`
- Runtime usage in `ResumeJDMatcher.__init__()` [matching_engine/matcher.py](matching_engine/matcher.py#L26)
- Weight adaptation logic in `_adapt_weights()` [matching_engine/matcher.py](matching_engine/matcher.py#L392)

### 4.6 ML model module (training/evaluation)
- Config keys in [config/config.yaml](config/config.yaml#L57):
  - `model_type`, `kernel`, `test_size`, `random_state`, `max_iterations`, `class_weight`, `cross_validation_folds`
- Runtime usage in `SkillClassifier.__init__()` and `_create_model()` [ml_model/classifier.py](ml_model/classifier.py#L32)
- Note: this module is not called by the main resume‑matching pipeline in [matching_engine/matcher.py](matching_engine/matcher.py).

## 5) Output artifacts

- CLI output is printed to stdout in [main.py](main.py#L42).
- Optional CSV/JSON output file is saved in [main.py](main.py#L71).
- Matching results DataFrame structure is assembled in [matching_engine/matcher.py](matching_engine/matcher.py#L298).
