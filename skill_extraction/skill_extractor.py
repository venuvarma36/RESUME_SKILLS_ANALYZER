"""
Skill Extraction Module for Resume Skill Recognition System
Combines NER-based and rule-based skill extraction.
"""

import re
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple, Any
from collections import defaultdict

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

try:  # optional deps
    import spacy
except Exception:  # noqa: BLE001
    spacy = None

try:
    from keybert import KeyBERT
except Exception:  # noqa: BLE001
    KeyBERT = None

try:
    from sentence_transformers import SentenceTransformer
except Exception:  # noqa: BLE001
    SentenceTransformer = None

try:
    from rake_nltk import Rake
except Exception:  # noqa: BLE001
    Rake = None

try:
    from rapidfuzz import process, fuzz
except Exception:  # noqa: BLE001
    process, fuzz = None, None

from utils import get_logger, config, load_json, deduplicate_list
from preprocessing import TextPreprocessor


logger = get_logger(__name__)

CATEGORY_KEYS = ['technical_skills', 'tools', 'frameworks', 'soft_skills', 'certifications']


class SkillExtractor:
    """Extracts skills from text using hybrid NER and rule-based approaches."""
    
    def __init__(self):
        """Initialize skill extractor with NER model and skill dictionary."""
        self.use_ner = config.get('skill_extraction.use_ner_model', True)
        self.use_deberta_ner = config.get('skill_extraction.use_deberta_ner', False)
        self.deberta_model_name = config.get('skill_extraction.deberta_model_name', 'microsoft/deberta-v3-base')
        self.use_spacy_ner = config.get('skill_extraction.use_spacy_ner', False)
        self.spacy_model_name = config.get('skill_extraction.spacy_model', 'en_core_web_sm')
        self.use_rule_based = config.get('skill_extraction.use_rule_based', True)
        self.use_rake = config.get('skill_extraction.use_rake', True)
        self.use_keybert = config.get('skill_extraction.use_keybert', True)
        self.keyword_top_n = config.get('skill_extraction.keyword_top_n', 15)
        self.confidence_threshold = config.get('skill_extraction.confidence_threshold', 0.7)
        self.deduplicate = config.get('skill_extraction.deduplicate', True)
        self.normalize_synonyms = config.get('skill_extraction.normalize_synonyms', True)
        self.canonicalize = config.get('skill_extraction.canonicalize', True)
        self.canonical_threshold = config.get('skill_extraction.canonical_match_threshold', 85)
        self.embedding_model_for_keywords = config.get('skill_extraction.keyword_embedding_model', 'sentence-transformers/all-MiniLM-L6-v2')
        self.enable_transferable_inference = config.get('skill_inference.enabled', True)
        self.inference_rules_path = config.get('skill_inference.rules_path', 'config/skill_inference_rules.json')
        
        # Load skill dictionary
        self.skill_dict = self._load_skill_dictionary()
        self._ontology_all = self._build_ontology_index(self.skill_dict)
        self.inference_rules = self._load_inference_rules()
        
        # Initialize NER model
        self.ner_pipeline = None
        if self.use_ner:
            self._initialize_ner_model()
        self.deberta_pipeline = None
        if self.use_deberta_ner:
            self._initialize_deberta_model()

        self.spacy_nlp = None
        if self.use_spacy_ner:
            self._initialize_spacy_model()
        
        # Initialize preprocessor
        self.preprocessor = TextPreprocessor(download_nltk_data=False)

        # Keyword expansion models
        self.rake = Rake() if (self.use_rake and Rake is not None) else None
        self.keybert_model = None
        if self.use_keybert and KeyBERT is not None:
            self._initialize_keybert()
        
        logger.info("SkillExtractor initialized with NER=%s, RuleBased=%s",
                   self.use_ner, self.use_rule_based)

    def _initialize_keybert(self) -> None:
        """Initialize KeyBERT with a CPU SentenceTransformer to avoid meta tensor issues."""
        if SentenceTransformer is None:
            logger.warning("sentence-transformers not available; disabling KeyBERT")
            self.use_keybert = False
            return
        try:
            logger.info("Loading KeyBERT embedding model on CPU: %s", self.embedding_model_for_keywords)
            st_model = SentenceTransformer(self.embedding_model_for_keywords, device='cpu')
            self.keybert_model = KeyBERT(model=st_model)
            logger.info("KeyBERT initialized successfully")
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to initialize KeyBERT: %s", exc)
            self.keybert_model = None
            self.use_keybert = False
    
    def _load_skill_dictionary(self) -> Dict[str, List[str]]:
        """
        Load skill dictionary from configuration.
        
        Returns:
            Skill dictionary
        """
        try:
            # Get project root
            project_root = Path(__file__).parent.parent
            skill_dict_path = project_root / "config" / "skills_dictionary.json"
            
            skill_dict = load_json(str(skill_dict_path))
            logger.info("Loaded skill dictionary with %d categories", len(skill_dict))
            return skill_dict
        except Exception as e:
            logger.error("Failed to load skill dictionary: %s", str(e))
            return {key: [] for key in CATEGORY_KEYS}

    def _build_ontology_index(self, skill_dict: Dict[str, List[str]]) -> set:
        """Build a lowercase ontology set for fast membership checks."""
        ontology = set()
        for category, skill_list in skill_dict.items():
            if category == 'synonyms':
                continue
            ontology.update([s.lower() for s in skill_list])
        return ontology

    def _load_inference_rules(self) -> Dict[str, Any]:
        """Load transferable skill inference rules from JSON config."""
        default_rules: Dict[str, Any] = {
            'single_skill_rules': {},
            'combination_rules': []
        }

        if not self.enable_transferable_inference:
            return default_rules

        try:
            project_root = Path(__file__).parent.parent
            rules_path = project_root / self.inference_rules_path

            if not rules_path.exists():
                logger.warning("Skill inference rules not found at %s; inference will run with defaults", rules_path)
                return default_rules

            rules = load_json(str(rules_path))
            if not isinstance(rules, dict):
                logger.warning("Invalid inference rules format; expected object, got %s", type(rules).__name__)
                return default_rules

            rules.setdefault('single_skill_rules', {})
            rules.setdefault('combination_rules', [])
            logger.info("Loaded transferable skill inference rules from %s", rules_path)
            return rules
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load skill inference rules: %s", exc)
            return default_rules
    
    def _initialize_ner_model(self):
        """Initialize NER model for skill extraction."""
        try:
            model_name = config.get('skill_extraction.ner_model_name', 
                                   'dslim/bert-base-NER')
            
            logger.info("Loading NER model: %s", model_name)
            
            # Check if CUDA is available
            device = 0 if torch.cuda.is_available() else -1
            
            self.ner_pipeline = pipeline(
                "ner",
                model=model_name,
                tokenizer=model_name,
                aggregation_strategy="simple",
                device=device
            )
            
            logger.info("NER model loaded successfully (device: %s)",
                       "GPU" if device >= 0 else "CPU")
            
        except Exception as e:
            logger.error("Failed to load NER model: %s", str(e))
            logger.warning("Falling back to rule-based extraction only")
            self.use_ner = False
            self.ner_pipeline = None

    def _initialize_deberta_model(self):
        """Initialize DeBERTa token classification pipeline when enabled."""
        try:
            model_name = self.deberta_model_name
            logger.info("Loading DeBERTa model for NER: %s", model_name)
            device = 0 if torch.cuda.is_available() else -1
            self.deberta_pipeline = pipeline(
                "token-classification",
                model=model_name,
                tokenizer=model_name,
                aggregation_strategy="simple",
                device=device
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load DeBERTa model: %s", exc)
            self.use_deberta_ner = False
            self.deberta_pipeline = None

    def _initialize_spacy_model(self):
        """Initialize spaCy model for SKILL tagging when available."""
        if spacy is None:
            logger.warning("spaCy not installed; disabling spaCy NER")
            self.use_spacy_ner = False
            return
        try:
            self.spacy_nlp = spacy.load(self.spacy_model_name)
            logger.info("Loaded spaCy model: %s", self.spacy_model_name)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load spaCy model %s: %s", self.spacy_model_name, exc)
            self.use_spacy_ner = False
            self.spacy_nlp = None
    
    def extract(self, text: str) -> Dict[str, List[str]]:
        """
        Extract skills from text using hybrid approach.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with categorized skills
        """
        if not text or not text.strip():
            return self._empty_result()
        
        # Extract using both methods
        ner_skills = self._extract_with_ner(text) if self.use_ner else {}
        deberta_skills = self._extract_with_deberta(text) if self.use_deberta_ner else {}
        spacy_skills = self._extract_with_spacy(text) if self.use_spacy_ner else {}
        rule_skills = self._extract_with_rules(text) if self.use_rule_based else {}
        
        # Merge results
        merged_skills = self._merge_skills(ner_skills, rule_skills)
        merged_skills = self._merge_skills(merged_skills, deberta_skills)
        merged_skills = self._merge_skills(merged_skills, spacy_skills)

        # Keyword expansion to seed ontology
        keywords = self._expand_keywords(text)
        if keywords:
            merged_skills['technical_skills'].extend(keywords)
        
        # Apply synonym normalization
        if self.normalize_synonyms:
            merged_skills = self._normalize_synonyms(merged_skills)
        
        # Deduplicate
        if self.deduplicate:
            merged_skills = self._deduplicate_skills(merged_skills)

        # Canonicalize to ontology using fuzzy matching
        merged_skills = self._canonicalize_skills(merged_skills)

        # Filter out terms not in ontology to reduce noise
        merged_skills = self._filter_to_ontology(merged_skills)
        
        return merged_skills
    
    def _extract_with_ner(self, text: str) -> Dict[str, List[str]]:
        """
        Extract skills using NER model.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with extracted skills
        """
        if not self.ner_pipeline:
            return {}
        
        try:
            # Run NER
            entities = self.ner_pipeline(text)
            
            # Filter by confidence and categorize
            skills = defaultdict(list)
            
            for entity in entities:
                if entity['score'] >= self.confidence_threshold:
                    word = entity['word'].strip()
                    entity_type = entity['entity_group']
                    
                    # Map entity types to skill categories
                    if entity_type in ['ORG', 'MISC']:
                        # Check which category it belongs to
                        category = self._categorize_skill(word)
                        skills[category].append(word)
            
            return dict(skills)
            
        except Exception as e:
            logger.error("NER extraction failed: %s", str(e))
            return {}

    def _extract_with_deberta(self, text: str) -> Dict[str, List[str]]:
        """Extract skills using DeBERTa token classification when enabled."""
        if not self.deberta_pipeline:
            return {}

        try:
            entities = self.deberta_pipeline(text)
            skills = defaultdict(list)
            for entity in entities:
                if entity['score'] >= self.confidence_threshold:
                    word = entity['word'].strip()
                    category = self._categorize_skill(word)
                    skills[category].append(word)
            return dict(skills)
        except Exception as exc:  # noqa: BLE001
            logger.error("DeBERTa extraction failed: %s", exc)
            return {}

    def _extract_with_spacy(self, text: str) -> Dict[str, List[str]]:
        """Extract skills using spaCy model; fallback to noun chunks if SKILL label absent."""
        if not self.spacy_nlp:
            return {}

        try:
            doc = self.spacy_nlp(text)
            skills = defaultdict(list)
            for ent in doc.ents:
                if ent.label_.lower() in ['skill', 'product', 'org']:
                    category = self._categorize_skill(ent.text)
                    skills[category].append(ent.text)
            # If no labeled entities, harvest noun chunks as weak signals
            if not skills:
                for chunk in doc.noun_chunks:
                    category = self._categorize_skill(chunk.text)
                    skills[category].append(chunk.text)
            return dict(skills)
        except Exception as exc:  # noqa: BLE001
            logger.error("spaCy extraction failed: %s", exc)
            return {}
    
    def _extract_with_rules(self, text: str) -> Dict[str, List[str]]:
        """
        Extract skills using rule-based matching.
        
        Args:
            text: Input text
            
        Returns:
            Dictionary with extracted skills
        """
        skills = {
            'technical_skills': [],
            'tools': [],
            'frameworks': [],
            'soft_skills': []
        }
        
        # Create case-insensitive patterns for each skill
        for category, skill_list in self.skill_dict.items():
            if category == 'synonyms' or category == 'certifications':
                continue
            
            for skill in skill_list:
                # Create regex pattern with word boundaries
                # Handle special characters in skill names
                escaped_skill = re.escape(skill)
                pattern = rf'\b{escaped_skill}\b'
                
                # Search case-insensitive
                if re.search(pattern, text, re.IGNORECASE):
                    skills[category].append(skill)
        
        return skills
    
    def _categorize_skill(self, skill: str) -> str:
        """
        Categorize a skill based on dictionary lookup.
        
        Args:
            skill: Skill name
            
        Returns:
            Category name
        """
        skill_lower = skill.lower()
        
        # Check each category
        for category, skill_list in self.skill_dict.items():
            if category in ['synonyms', 'certifications']:
                continue
            
            for dict_skill in skill_list:
                if skill_lower == dict_skill.lower():
                    return category
        
        # Default to technical_skills
        return 'technical_skills'
    
    def _merge_skills(self, skills1: Dict[str, List[str]], 
                      skills2: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Merge two skill dictionaries.
        
        Args:
            skills1: First skill dictionary
            skills2: Second skill dictionary
            
        Returns:
            Merged skill dictionary
        """
        merged = defaultdict(list)
        
        # Add skills from both dictionaries
        for skills_dict in [skills1, skills2]:
            for category, skill_list in skills_dict.items():
                merged[category].extend(skill_list)
        
        # Ensure all categories exist
        for category in CATEGORY_KEYS:
            if category not in merged:
                merged[category] = []
        
        return dict(merged)

    def _expand_keywords(self, text: str) -> List[str]:
        """Expand domain terms using RAKE/KeyBERT when available."""
        keywords: List[str] = []
        if self.rake:
            try:
                self.rake.extract_keywords_from_text(text)
                # rake returns (score, phrase); keep phrase only
                rake_pairs = self.rake.get_ranked_phrases_with_scores()
                for score, phrase in rake_pairs:
                    if isinstance(phrase, str) and phrase.strip():
                        keywords.append(phrase)
                        if len(keywords) >= self.keyword_top_n:
                            break
            except Exception as exc:  # noqa: BLE001
                logger.debug("RAKE keyword extraction failed: %s", exc)
        if self.keybert_model:
            try:
                kb = self.keybert_model.extract_keywords(text, top_n=self.keyword_top_n)
                for kw, _ in kb:
                    if isinstance(kw, str) and kw.strip():
                        keywords.append(kw)
            except Exception as exc:  # noqa: BLE001
                logger.debug("KeyBERT extraction failed: %s", exc)
        # Guard against non-strings from upstream
        keywords = [str(k) for k in keywords if isinstance(k, (str, bytes)) or k is not None]
        return deduplicate_list(keywords, case_sensitive=False)

    def _canonicalize_skills(self, skills: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Canonicalize skills to ontology using RapidFuzz matching."""
        if not self.canonicalize or process is None:
            return skills

        ontology = {}
        for category, skill_list in self.skill_dict.items():
            if category == 'synonyms':
                continue
            for s in skill_list:
                ontology[s] = category

        canonicalized = {cat: [] for cat in CATEGORY_KEYS}

        for category, skill_list in skills.items():
            for skill in skill_list:
                match = process.extractOne(skill, list(ontology.keys()), scorer=fuzz.WRatio)
                if match and match[1] >= self.canonical_threshold:
                    canonical = match[0]
                    target_category = ontology.get(canonical, category)
                    canonicalized[target_category].append(canonical)
                else:
                    canonicalized[category].append(skill)

        # Deduplicate
        for category in canonicalized:
            canonicalized[category] = deduplicate_list(canonicalized[category], case_sensitive=False)

        return canonicalized

    def _filter_to_ontology(self, skills: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """Keep only skills present in ontology to reduce non-skill noise."""
        filtered = {cat: [] for cat in CATEGORY_KEYS}
        for category, skill_list in skills.items():
            for skill in skill_list:
                if skill.lower() in self._ontology_all:
                    filtered[category].append(skill)
        # Deduplicate again after filtering
        for category in filtered:
            filtered[category] = deduplicate_list(filtered[category], case_sensitive=False)
        return filtered
    
    def _normalize_synonyms(self, skills: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Normalize skill synonyms.
        
        Args:
            skills: Skill dictionary
            
        Returns:
            Normalized skill dictionary
        """
        synonyms = self.skill_dict.get('synonyms', {})
        
        normalized = {}
        for category, skill_list in skills.items():
            normalized_list = []
            
            for skill in skill_list:
                # Check if it's a synonym
                normalized_skill = synonyms.get(skill, skill)
                normalized_list.append(normalized_skill)
            
            normalized[category] = normalized_list
        
        return normalized

    def infer_transferable_skills(self, skills: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Infer related/transferable skills from explicitly extracted skills.

        Args:
            skills: Explicitly extracted and categorized skills

        Returns:
            Dictionary of inferred skills by category
        """
        inferred = self._empty_result()
        if not self.enable_transferable_inference:
            return inferred

        explicit_lower = {
            s.lower()
            for skill_list in skills.values()
            for s in skill_list
            if isinstance(s, str) and s.strip()
        }

        if not explicit_lower:
            return inferred

        ontology_category = {}
        for category, skill_list in self.skill_dict.items():
            if category == 'synonyms':
                continue
            for item in skill_list:
                if isinstance(item, str):
                    ontology_category[item.lower()] = category

        def _add_target(target_skill: str) -> None:
            skill_lower = target_skill.lower()
            if skill_lower in explicit_lower:
                return
            if skill_lower not in self._ontology_all:
                return
            target_category = ontology_category.get(skill_lower, 'technical_skills')
            inferred[target_category].append(target_skill)

        single_rules = self.inference_rules.get('single_skill_rules', {})
        if isinstance(single_rules, dict):
            for source_skill, targets in single_rules.items():
                if not isinstance(source_skill, str):
                    continue
                if source_skill.lower() not in explicit_lower:
                    continue
                for target_skill in targets or []:
                    if isinstance(target_skill, str):
                        _add_target(target_skill)

        combo_rules = self.inference_rules.get('combination_rules', [])
        if isinstance(combo_rules, list):
            for rule in combo_rules:
                if not isinstance(rule, dict):
                    continue
                requires = [r.lower() for r in rule.get('requires', []) if isinstance(r, str)]
                if not requires or not set(requires).issubset(explicit_lower):
                    continue
                for target_skill in rule.get('infer', []) or []:
                    if isinstance(target_skill, str):
                        _add_target(target_skill)

        for category in inferred:
            inferred[category] = deduplicate_list(inferred[category], case_sensitive=False)

        return inferred
    
    def _is_valid_skill(self, skill: str) -> bool:
        """
        Validate if extracted skill is legitimate.
        
        Args:
            skill: Skill to validate
            
        Returns:
            True if valid, False otherwise
        """
        if not skill or not skill.strip():
            return False
        
        skill = skill.strip()
        
        # Filter out single characters (except C for C language)
        if len(skill) == 1 and skill.upper() != 'C':
            return False
        
        # Filter out skills starting with special characters
        if skill[0] in ['#', '$', '@', '%', '&', '*', '!', '~']:
            return False
        
        # Whitelist for valid 2-character skills
        valid_2char_skills = ['C', 'R', 'Go', 'AI', 'ML', 'CI', 'CD', 'JS', 'TS']
        if len(skill) == 2:
            # Only allow if in whitelist (case-insensitive)
            if skill.upper() not in [s.upper() for s in valid_2char_skills]:
                return False
        
        # Filter out very short skills (less than 3 chars) except whitelisted
        if len(skill) < 3 and skill.upper() not in [s.upper() for s in valid_2char_skills]:
            return False
        
        # Filter out skills that are just numbers
        if skill.isdigit():
            return False
        
        # Filter out common garbage patterns
        garbage_patterns = [
            r'^\d+$',  # Only numbers
            r'^[^a-zA-Z]+$',  # No letters at all
            r'^\W+$',  # Only special characters
        ]
        
        for pattern in garbage_patterns:
            if re.match(pattern, skill):
                return False
        
        return True
    
    def _deduplicate_skills(self, skills: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Remove duplicate skills within each category.
        
        Args:
            skills: Skill dictionary
            
        Returns:
            Deduplicated skill dictionary
        """
        deduplicated = {}
        
        for category, skill_list in skills.items():
            # First validate skills, then deduplicate
            valid_skills = [s for s in skill_list if self._is_valid_skill(s)]
            deduplicated[category] = deduplicate_list(valid_skills, case_sensitive=False)
        
        return deduplicated
    
    def _empty_result(self) -> Dict[str, List[str]]:
        """
        Return empty result structure.
        
        Returns:
            Empty skill dictionary
        """
        return {
            'technical_skills': [],
            'tools': [],
            'frameworks': [],
            'soft_skills': [],
            'certifications': []
        }
    
    def extract_batch(self, texts: List[str]) -> List[Dict[str, List[str]]]:
        """
        Extract skills from multiple texts.
        
        Args:
            texts: List of texts
            
        Returns:
            List of skill dictionaries
        """
        logger.info("Extracting skills from batch of %d texts", len(texts))
        return [self.extract(text) for text in texts]
    
    def get_all_skills_flat(self, skills: Dict[str, List[str]]) -> List[str]:
        """
        Get all skills as a flat list.
        
        Args:
            skills: Skill dictionary
            
        Returns:
            Flat list of all skills
        """
        all_skills = []
        for skill_list in skills.values():
            all_skills.extend(skill_list)
        return deduplicate_list(all_skills, case_sensitive=False)


def extract_skills(text: str) -> Dict[str, List[str]]:
    """
    Convenience function to extract skills from text.
    
    Args:
        text: Input text
        
    Returns:
        Dictionary with categorized skills
    """
    extractor = SkillExtractor()
    return extractor.extract(text)
