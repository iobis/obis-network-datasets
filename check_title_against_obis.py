import os
import requests
from github import Github
import time

def search_obis_dataset(dataset_title):
    """
    Search for a dataset in OBIS using exact title match
    Returns: (found: bool, dataset_url: str or None)
    """
    url = "https://api.obis.org/dataset/search2"
    params = {
        'q': dataset_title,
        'size': 20  # Get more results to check for exact matches
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data and 'results' in data:
            for result in data['results']:
                # Check for exact title match (case-insensitive)
                if result.get('title', '').strip().lower() == dataset_title.strip().lower():
                    dataset_id = result.get('id')
                    if dataset_id:
                        dataset_url = f"https://obis.org/dataset/{dataset_id}"
                        return True, dataset_url
        
        return False, None
        
    except Exception as e:
        print(f"Error searching OBIS for '{dataset_title}': {e}")
        return None, None

def main():
    # Initialize GitHub client
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("ERROR: GITHUB_TOKEN not found")
        return
    
    g = Github(github_token)
    
    # Get the repository
    repo = g.get_repo("iobis/obis-network-datasets")
    
    # Ensure the label exists
    try:
        repo.get_label("In OBIS")
        print("Label 'In OBIS' exists")
    except:
        print("Creating label 'In OBIS'")
        repo.create_label("In OBIS", "1d76db", "Dataset already exists in OBIS")
    
    # Get all open issues
    open_issues = repo.get_issues(state='open')
    
    checked_count = 0
    found_count = 0
    
    for issue in open_issues:
        # Skip if already labeled as "In OBIS"
        label_names = [label.name for label in issue.labels]
        if "In OBIS" in label_names:
            print(f"Skipping issue #{issue.number} (already labeled)")
            continue
        
        dataset_title = issue.title
        print(f"Checking issue #{issue.number}: {dataset_title}")
        
        # Search OBIS for exact match
        found, dataset_url = search_obis_dataset(dataset_title)
        
        if found is True:
            found_count += 1
            print(f"  ✓ Found exact match in OBIS: {dataset_url}")
            
            # Check if we've already commented about this
            existing_comments = [c for c in issue.get_comments() 
                               if 'The dataset is in OBIS:' in c.body]
            
            if not existing_comments:
                # Add comment
                comment_body = f"The dataset is in OBIS: {dataset_url}"
                issue.create_comment(comment_body)
                print(f"  ✓ Added comment")
            else:
                print(f"  ℹ Already commented")
            
            # Add label
            issue.add_to_labels("In OBIS")
            print(f"  ✓ Added 'In OBIS' label")
            
        elif found is False:
            print(f"  ✗ Not found in OBIS")
        else:
            print(f"  ⚠ Error checking OBIS")
        
        checked_count += 1
        
        # Rate limiting - be respectful to the API
        time.sleep(1)
    
    print(f"\n{'='*50}")
    print(f"Summary: Checked {checked_count} issues")
    print(f"Found {found_count} datasets already in OBIS")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
