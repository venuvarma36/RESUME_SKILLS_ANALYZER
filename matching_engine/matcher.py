"""
Matching Engine Module for Resume Skill Recognition System
Matches resumes to job descriptions based on skill similarity.
"""

from typing import List, Dict, Tuple, Optional
import numpy as np
import pandas as pd

from text_extraction import TextExtractor
from preprocessing import TextPreprocessor
from skill_extraction import SkillExtractor
from feature_engineering import FeatureEngineer
from utils import (
    get_logger, config, calculate_overlap, 
    format_percentage, safe_divide
)


logger = get_logger(__name__)

try:
    from blockchain.secure_storage import SecureDataStorage
    BLOCKCHAIN_AVAILABLE = True
except Exception as e:  # noqa: BLE001
    BLOCKCHAIN_AVAILABLE = False
    logger.warning("Blockchain module not available: %s", str(e))


class ResumeJDMatcher:
    """Matches resumes to job descriptions using skill-based similarity."""
    
    def __init__(self):
        """Initialize matcher with all required components."""
        self.text_extractor = TextExtractor()
        self.preprocessor = TextPreprocessor(download_nltk_data=False)
        self.skill_extractor = SkillExtractor()
        self.feature_engineer = FeatureEngineer()

        # Initialize blockchain secure storage if enabled
        self.blockchain_enabled = config.get('blockchain.enabled', False) and BLOCKCHAIN_AVAILABLE
        if self.blockchain_enabled:
            try:
                self.secure_storage = SecureDataStorage()
                logger.info("Blockchain secure storage initialized")
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to initialize blockchain secure storage: %s", exc)
                self.blockchain_enabled = False
                self.secure_storage = None
        else:
            self.secure_storage = None
            if config.get('blockchain.enabled', False) and not BLOCKCHAIN_AVAILABLE:
                logger.warning("Blockchain enabled in config but module not available")
        
        # Load configuration
        self.similarity_metric = config.get('matching.similarity_metric', 'cosine')
        self.weights = {
            'technical_skills': config.get('matching.weights.technical_skills', 0.5),
            'tools': config.get('matching.weights.tools', 0.3),
            'frameworks': config.get('matching.weights.frameworks', 0.15),
            'soft_skills': config.get('matching.weights.soft_skills', 0.05)
        }
        self.min_threshold = config.get('matching.min_match_threshold', 0.3)
        self.adaptive_weights = config.get('matching.domain_adaptive_weights', True)
        self.shap_enabled = config.get('matching.shap_enabled', True)
        
        logger.info("ResumeJDMatcher initialized with weights: %s", self.weights)
        logger.info("Blockchain encryption: %s", "ENABLED" if self.blockchain_enabled else "DISABLED")
    
    def process_resume(self, resume_path: str) -> Dict[str, any]:
        """
        Process a single resume.
        
        Args:
            resume_path: Path to resume file
            
        Returns:
            Dictionary with processed resume data
        """
        logger.info("Processing resume: %s", resume_path)
        
        # Extract text
        extraction_result = self.text_extractor.extract(resume_path)
        
        if not extraction_result['success']:
            logger.error("Failed to extract text from resume: %s",
                        extraction_result['error'])
            return {
                'file_path': resume_path,
                'success': False,
                'error': extraction_result['error'],
                'text': '',
                'skills': {},
                'embedding': None,
                'pages': extraction_result.get('pages', []),
                'tables': extraction_result.get('tables', [])
            }
        
        text = extraction_result['text']
        
        # Extract skills
        skills = self.skill_extractor.extract(text)

        # Attach provenance: map skills to pages and bounding boxes when available
        skill_evidence = self._attach_skill_evidence(skills, extraction_result.get('pages', []))
        
        # Generate embedding
        embedding = self.feature_engineer.generate_weighted_skill_embedding(
            skills, self.weights
        )

        resume_data = {
            'file_path': resume_path,
            'success': True,
            'error': None,
            'text': text,
            'skills': skills,
            'embedding': embedding,
            'extraction_method': extraction_result['method'],
            'pages': extraction_result.get('pages', []),
            'tables': extraction_result.get('tables', []),
            'skill_evidence': skill_evidence
        }

        # Store in blockchain if enabled
        if self.blockchain_enabled and self.secure_storage:
            try:
                storage_metadata = self.secure_storage.store_resume(resume_data)
                resume_data['blockchain_block'] = storage_metadata['block_index']
                resume_data['blockchain_hash'] = storage_metadata['block_hash']
                logger.info("Resume stored in blockchain at block #%d", storage_metadata['block_index'])
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to store resume in blockchain: %s", exc)

        return resume_data
    
    def process_job_description(self, jd_text: str) -> Dict[str, any]:
        """
        Process job description text.
        
        Args:
            jd_text: Job description text
            
        Returns:
            Dictionary with processed JD data
        """
        logger.info("Processing job description (%d chars)", len(jd_text))
        
        if not jd_text or not jd_text.strip():
            return {
                'text': '',
                'skills': {},
                'embedding': None,
                'success': False,
                'error': 'Empty job description'
            }
        
        # Extract skills
        skills = self.skill_extractor.extract(jd_text)
        
        # Generate embedding
        embedding = self.feature_engineer.generate_weighted_skill_embedding(
            skills, self.weights
        )

        jd_data = {
            'text': jd_text,
            'skills': skills,
            'embedding': embedding,
            'success': True,
            'error': None
        }

        # Store in blockchain if enabled
        if self.blockchain_enabled and self.secure_storage:
            try:
                storage_metadata = self.secure_storage.store_job_description(jd_data)
                jd_data['blockchain_block'] = storage_metadata['block_index']
                jd_data['blockchain_hash'] = storage_metadata['block_hash']
                logger.info("Job description stored in blockchain at block #%d", storage_metadata['block_index'])
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to store job description in blockchain: %s", exc)

        return jd_data
    
    def compute_match_score(self, resume_data: Dict, jd_data: Dict) -> Dict[str, any]:
        """
        Compute match score between resume and job description.
        
        Args:
            resume_data: Processed resume data
            jd_data: Processed JD data
            
        Returns:
            Dictionary with match scores and details
        """
        if not resume_data['success'] or not jd_data['success']:
            return {
                'overall_score': 0.0,
                'category_scores': {},
                'skill_overlap': {},
                'matched_skills': [],
                'missing_skills': [],
                'match_percentage': format_percentage(0.0)
            }
        
        # Optionally adapt weights based on JD domain hints
        weights = self._adapt_weights(jd_data['text']) if self.adaptive_weights else self.weights

        # Compute embedding similarity
        embedding_similarity = self.feature_engineer.compute_similarity(
            resume_data['embedding'],
            jd_data['embedding']
        )
        
        # Compute category-wise scores
        category_scores = {}
        for category in ['technical_skills', 'tools', 'frameworks', 'soft_skills']:
            resume_skills = set(s.lower() for s in resume_data['skills'].get(category, []))
            jd_skills = set(s.lower() for s in jd_data['skills'].get(category, []))
            
            if jd_skills:
                overlap = resume_skills & jd_skills
                category_score = len(overlap) / len(jd_skills)
            else:
                category_score = 1.0 if not resume_skills else 0.5
            
            category_scores[category] = category_score
        
        # Compute weighted overall score
        overall_score = sum(
            category_scores[cat] * weights[cat]
            for cat in category_scores
        )
        
        # Adjust with embedding similarity
        # Quadruple similarity fusion (augmented with context/domain signals)
        quad_features = self.feature_engineer.compute_quadruple_features(
            resume_data['text'], jd_data['text'],
            resume_data['skills'], jd_data['skills']
        )

        quad_score = self.feature_engineer.hybrid_similarity(quad_features)

        # Meta score combines category score, embedding similarity, and fused similarity
        final_score = (
            0.4 * overall_score +
            0.2 * embedding_similarity +
            0.4 * quad_score
        )

        shap_values = self.feature_engineer.explain_with_shap(quad_features)
        
        # Get skill overlap details
        all_resume_skills = set(s.lower() for skills in resume_data['skills'].values() 
                               for s in skills)
        all_jd_skills = set(s.lower() for skills in jd_data['skills'].values() 
                           for s in skills)
        
        matched_skills = list(all_resume_skills & all_jd_skills)
        missing_skills = list(all_jd_skills - all_resume_skills)
        
        return {
            'overall_score': final_score,
            'embedding_similarity': embedding_similarity,
            'quad_score': quad_score,
            'quad_features': quad_features,
            'category_scores': category_scores,
            'matched_skills': matched_skills,
            'missing_skills': missing_skills,
            'match_percentage': format_percentage(final_score),
            'shap_values': shap_values
        }

    def _attach_skill_evidence(self, skills: Dict[str, List[str]], pages: List[Dict[str, any]]) -> Dict[str, List[Dict[str, any]]]:
        """Map extracted skills to page-level evidence with bounding boxes when available."""
        evidence: Dict[str, List[Dict[str, any]]] = {}
        if not pages:
            return evidence

        # Build searchable page texts and block-level bboxes
        for category, skill_list in skills.items():
            for skill in skill_list:
                skill_lower = skill.lower()
                evidence_entries = []
                for page in pages:
                    page_text = page.get('text', '') or ''
                    if skill_lower in page_text.lower():
                        entry = {
                            'page': page.get('page_number'),
                            'bbox': None,
                            'method': 'text'
                        }
                        # Try to find a block containing the skill text to surface bbox
                        for block in page.get('blocks', []) or []:
                            block_text = block.get('text', '') or ''
                            if skill_lower in block_text.lower():
                                entry['bbox'] = block.get('bbox')
                                entry['method'] = 'layout'
                                break
                        evidence_entries.append(entry)
                if evidence_entries:
                    evidence[skill] = evidence_entries
        return evidence
    
    def match_resumes_to_jd(self, resume_paths: List[str], 
                           jd_text: str) -> pd.DataFrame:
        """
        Match multiple resumes to a job description.
        
        Args:
            resume_paths: List of resume file paths
            jd_text: Job description text
            
        Returns:
            DataFrame with match results, sorted by score
        """
        logger.info("Matching %d resumes to job description", len(resume_paths))
        
        # Process job description
        jd_data = self.process_job_description(jd_text)
        
        if not jd_data['success']:
            logger.error("Failed to process job description: %s", jd_data['error'])
            return pd.DataFrame()
        
        # Process all resumes and compute matches
        results = []
        
        for i, resume_path in enumerate(resume_paths):
            logger.info("Processing resume %d/%d", i + 1, len(resume_paths))
            
            # Process resume
            resume_data = self.process_resume(resume_path)
            
            # Compute match score
            match_result = self.compute_match_score(resume_data, jd_data)
            
            # Compile result
            # Collect all extracted skills from resume
            all_extracted = []
            for category, skills in resume_data['skills'].items():
                all_extracted.extend(skills)
            
            result = {
                'resume_file': resume_path,
                'overall_score': match_result['overall_score'],
                'match_percentage': match_result.get('match_percentage', format_percentage(match_result.get('overall_score', 0.0))),
                'embedding_similarity': match_result.get('embedding_similarity', 0.0),
                'quad_score': match_result.get('quad_score', 0.0),
                'technical_skills_score': match_result['category_scores'].get('technical_skills', 0.0),
                'tools_score': match_result['category_scores'].get('tools', 0.0),
                'frameworks_score': match_result['category_scores'].get('frameworks', 0.0),
                'soft_skills_score': match_result['category_scores'].get('soft_skills', 0.0),
                'matched_skills_count': len(match_result['matched_skills']),
                'missing_skills_count': len(match_result['missing_skills']),
                'all_extracted_skills': ', '.join(sorted(set(all_extracted))),  # All unique skills
                'matched_skills': ', '.join(match_result['matched_skills'][:10]),  # Top 10
                'missing_skills': ', '.join(match_result['missing_skills'][:10]),  # Top 10
                'extraction_success': resume_data['success'],
                'extraction_method': resume_data.get('extraction_method', 'unknown'),
                'quad_semantic': match_result.get('quad_features', {}).get('semantic', 0.0),
                'quad_jaccard': match_result.get('quad_features', {}).get('jaccard', 0.0),
                'quad_fuzzy': match_result.get('quad_features', {}).get('fuzzy', 0.0),
                'quad_graph': match_result.get('quad_features', {}).get('graph', 0.0),
                'context_match': match_result.get('quad_features', {}).get('context_match', 0.0),
                'domain_relevance': match_result.get('quad_features', {}).get('domain_relevance', 0.0),
                'shap_values': match_result.get('shap_values'),
                'pages': resume_data.get('pages', []),
                'tables': resume_data.get('tables', []),
                'skill_evidence': resume_data.get('skill_evidence', {})
            }
            
            results.append(result)
        
        # Create DataFrame and sort by score
        df = pd.DataFrame(results)
        
        if not df.empty:
            df = df.sort_values('overall_score', ascending=False)
            df['rank'] = range(1, len(df) + 1)
            
            # Reorder columns
            cols = ['rank', 'resume_file', 'overall_score', 'match_percentage'] + \
                   [col for col in df.columns if col not in ['rank', 'resume_file', 
                    'overall_score', 'match_percentage']]
            df = df[cols]
        
        logger.info("Matching complete. Top score: %.4f", 
                   df['overall_score'].max() if not df.empty else 0.0)
        
        return df
    
    def get_detailed_match_report(self, resume_path: str, 
                                 jd_text: str) -> Dict[str, any]:
        """
        Get detailed match report for a single resume.
        
        Args:
            resume_path: Path to resume file
            jd_text: Job description text
            
        Returns:
            Detailed match report
        """
        logger.info("Generating detailed match report")
        
        # Process resume and JD
        resume_data = self.process_resume(resume_path)
        jd_data = self.process_job_description(jd_text)
        
        # Compute match
        match_result = self.compute_match_score(resume_data, jd_data)
        
        # Calculate category-wise overlap
        category_overlap = {}
        for category in ['technical_skills', 'tools', 'frameworks', 'soft_skills']:
            resume_skills = resume_data['skills'].get(category, [])
            jd_skills = jd_data['skills'].get(category, [])
            
            overlap = calculate_overlap(resume_skills, jd_skills, case_sensitive=False)
            category_overlap[category] = overlap
        
        return {
            'resume_file': resume_path,
            'overall_score': match_result['overall_score'],
            'match_percentage': match_result['match_percentage'],
            'category_scores': match_result['category_scores'],
            'quad_features': match_result.get('quad_features', {}),
            'quad_score': match_result.get('quad_score', 0.0),
            'category_overlap': category_overlap,
            'matched_skills': match_result['matched_skills'],
            'missing_skills': match_result['missing_skills'],
            'resume_skills': resume_data['skills'],
            'jd_skills': jd_data['skills'],
            'extraction_method': resume_data.get('extraction_method', 'unknown')
        }

    def _adapt_weights(self, jd_text: str) -> Dict[str, float]:
        """Lightweight domain-aware weight nudging based on keywords."""
        lowered = jd_text.lower()
        weights = dict(self.weights)

        tech_cues = ['engineer', 'developer', 'ml', 'ai', 'data', 'software']
        soft_cues = ['manager', 'leadership', 'communication', 'stakeholder']

        if any(word in lowered for word in tech_cues):
            weights['technical_skills'] = min(0.6, weights['technical_skills'] + 0.1)
        if any(word in lowered for word in soft_cues):
            weights['soft_skills'] = min(0.15, weights['soft_skills'] + 0.05)

        # Renormalize
        total = sum(weights.values())
        for key in weights:
            weights[key] = weights[key] / total if total else weights[key]
        return weights


def match_resume_to_jd(resume_path: str, jd_text: str) -> float:
    """
    Convenience function to match a resume to a job description.
    
    Args:
        resume_path: Path to resume file
        jd_text: Job description text
        
    Returns:
        Match score (0 to 1)
    """
    matcher = ResumeJDMatcher()
    resume_data = matcher.process_resume(resume_path)
    jd_data = matcher.process_job_description(jd_text)
    match_result = matcher.compute_match_score(resume_data, jd_data)
    return match_result['overall_score']
