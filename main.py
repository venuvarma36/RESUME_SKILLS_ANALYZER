"""
Main entry point for Resume Skill Recognition System
Provides command-line interface for the system.
"""

import argparse
import sys
from pathlib import Path

from matching_engine import ResumeJDMatcher
from utils import config, LoggerManager, get_logger, save_json


# Initialize logging
LoggerManager.setup_logging(
    level=config.get('logging.level', 'INFO'),
    log_to_file=config.get('logging.log_to_file', True),
    log_to_console=config.get('logging.log_to_console', True),
    log_dir=str(config.get_path('logs_dir'))
)

logger = get_logger(__name__)


def match_resumes(resume_paths: list, jd_text: str, output_path: str = None):
    """
    Match resumes to job description.
    
    Args:
        resume_paths: List of resume file paths
        jd_text: Job description text
        output_path: Optional path to save results
    """
    logger.info("Starting resume matching process")
    
    # Initialize matcher
    matcher = ResumeJDMatcher()
    
    # Perform matching
    results_df = matcher.match_resumes_to_jd(resume_paths, jd_text)
    
    # Display results
    print("\n" + "="*80)
    print("RESUME MATCHING RESULTS")
    print("="*80 + "\n")
    
    if results_df.empty:
        print("No results generated.")
        return
    
    # Display summary
    print(f"Total Candidates: {len(results_df)}")
    print(f"Best Match: {results_df.iloc[0]['match_percentage']}")
    print(f"Average Score: {results_df['overall_score'].mean() * 100:.1f}%")
    print(f"Qualified (≥50%): {(results_df['overall_score'] >= 0.5).sum()}")
    print("\n")
    
    # Display top 10 results
    print("TOP 10 CANDIDATES:")
    print("-" * 80)
    
    display_cols = ['rank', 'resume_file', 'match_percentage', 'matched_skills_count',
                    'missing_skills_count']
    
    for idx, row in results_df.head(10).iterrows():
        print(f"\n{row['rank']}. {Path(row['resume_file']).name}")
        print(f"   Match: {row['match_percentage']}")
        print(f"   Matched Skills: {row['matched_skills_count']}")
        print(f"   Missing Skills: {row['missing_skills_count']}")
    
    # Save results if output path provided
    if output_path:
        output_path = Path(output_path)
        
        if output_path.suffix == '.json':
            results_df.to_json(output_path, orient='records', indent=2)
        elif output_path.suffix == '.csv':
            results_df.to_csv(output_path, index=False)
        else:
            # Default to CSV
            output_path = output_path.with_suffix('.csv')
            results_df.to_csv(output_path, index=False)
        
        print(f"\n✓ Results saved to: {output_path}")
        logger.info("Results saved to %s", output_path)
    
    print("\n" + "="*80 + "\n")


def main():
    """Main function for CLI."""
    logger.info("Python executable: %s", sys.executable)
    parser = argparse.ArgumentParser(
        description='Resume Skill Recognition & Matching System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Launch web UI
  python main.py --ui
  
  # Match resumes from command line
  python main.py --resumes resume1.pdf resume2.pdf --jd job_description.txt
  
  # Match with output file
  python main.py --resumes resumes/*.pdf --jd jd.txt --output results.csv
        """
    )
    
    parser.add_argument(
        '--ui',
        action='store_true',
        help='Launch Streamlit web interface'
    )
    
    parser.add_argument(
        '--resumes',
        nargs='+',
        help='Paths to resume files'
    )
    
    parser.add_argument(
        '--jd',
        help='Path to job description file or text'
    )
    
    parser.add_argument(
        '--output',
        help='Output file path for results (CSV or JSON)'
    )
    
    parser.add_argument(
        '--test',
        action='store_true',
        help='Run unit tests'
    )
    
    args = parser.parse_args()
    
    # Launch UI
    if args.ui:
        logger.info("Launching Streamlit UI")
        import subprocess
        subprocess.run([
            sys.executable, '-m', 'streamlit', 'run',
            str(Path(__file__).parent / 'ui' / 'app.py')
        ])
        return
    
    # Run tests
    if args.test:
        logger.info("Running unit tests")
        import pytest
        pytest.main([str(Path(__file__).parent / 'tests'), '-v'])
        return
    
    # CLI matching
    if args.resumes and args.jd:
        # Load job description
        jd_path = Path(args.jd)
        if jd_path.exists():
            with open(jd_path, 'r', encoding='utf-8') as f:
                jd_text = f.read()
        else:
            jd_text = args.jd
        
        # Match resumes
        match_resumes(args.resumes, jd_text, args.output)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
