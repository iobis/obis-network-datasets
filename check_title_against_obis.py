import os
import requests
from github import Github, Auth
import time
import re
import sys

# DRY RUN MODE - set to True to test without making any changes
DRY_RUN = os.environ.get('DRY_RUN', 'false').lower() == 'true'

def extract_urls_from_issue(issue_body):
    """
    Extract all URLs from the issue body
    """
    if not issue_body:
        return []
    
    # Find all URLs in the issue body
    url_pattern = r'https?://[^\s<>"\')]+|www\.[^\s<>"\')]+'
    urls = re.findall(url_pattern, issue_body)
    
    # Also extract UUIDs that might be GBIF dataset IDs
    uuid_pattern = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    uuids = re.findall(uuid_pattern, issue_body, re.IGNORECASE)
    
    # Add GBIF dataset URLs for found UUIDs
    for uuid in uuids:
        urls.append(f"https://www.gbif.org/dataset/{uuid}")
    
    return list(set(urls))  # Remove duplicates

def check_url_match_simple(issue_urls, obis_urls):
    """
    Check if any URLs from the issue match the OBIS URLs
    Returns: bool
    """
    if not obis_urls:
        return False
    
    # Normalize URLs for comparison
    def normalize_url(url):
        url = url.lower()
        url = url.replace('https://', '').replace('http://', '')
        url = url.rstrip('/')
        return url
    
    def extract_resource_id(url):
        """Extract the resource ID from IPT URLs (e.g., ?r=dataset_name)"""
        match = re.search(r'[?&]r=([^&]+)', url)
        return match.group(1) if match else None
    
    # Try exact matches first
    normalized_issue_urls = [normalize_url(url) for url in issue_urls]
    normalized_obis_urls = [normalize_url(url) for url in obis_urls if url]
    
    for issue_url in normalized_issue_urls:
        for obis_url in normalized_obis_urls:
            # Exact match (ignoring protocol)
            if issue_url == obis_url:
                return True
            
            # One contains the other (for partial URLs)
            if issue_url in obis_url or obis_url in issue_url:
                return True
    
    # Also check if they share the same IPT resource ID
    for issue_url in issue_urls:
        issue_resource = extract_resource_id(issue_url)
        if issue_resource:
            for obis_url in obis_urls:
                obis_resource = extract_resource_id(obis_url)
                if obis_resource and issue_resource.lower() == obis_resource.lower():
                    return True
    
    return False

def search_obis_dataset(dataset_title, issue_urls):
    """
    Search for a dataset in OBIS using exact title match and URL verification
    Returns: (title_match: bool, url_match: bool, dataset_url: str or None, obis_urls: list)
    """
    url = "https://api.obis.org/dataset/search2"
    params = {
        'q': dataset_title,
        'size': 20
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
                        
                        # Get URLs directly from the search result
                        obis_urls = []
                        if result.get('url'):
                            obis_urls.append(result['url'])
                        if result.get('feed'):
                            obis_urls.append(result['feed'])
                        if result.get('archive'):
                            obis_urls.append(result['archive'])
                        
                        # Check if URLs match
                        url_match = check_url_match_simple(issue_urls, obis_urls)
                        
                        return True, url_match, dataset_url, obis_urls
        
        return False, False, None, []
        
    except Exception as e:
        print(f"  Error searching OBIS: {e}")
        return None, None, None, []

def main():
    if DRY_RUN:
        print("=" * 60)
        print("🔍 DRY RUN MODE - No changes will be made to GitHub")
        print("=" * 60)
    
    # Initialize GitHub client
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("ERROR: GITHUB_TOKEN not found")
        return
    
    auth = Auth.Token(github_token)
    g = Github(auth=auth)
    
    # Get the repository
    repo = g.get_repo("iobis/obis-network-datasets")
    
    # Ensure the label exists (only if not dry run)
    if not DRY_RUN:
        try:
            repo.get_label("In OBIS")
            print("Label 'In OBIS' exists")
        except:
            print("Creating label 'In OBIS'")
            repo.create_label("In OBIS", "1d76db", "Dataset already exists in OBIS")
    
    # Get all open issues only
    print("Fetching open issues...")
    open_issues = list(repo.get_issues(state='open'))
    
    # Filter out pull requests
    open_issues = [issue for issue in open_issues if not issue.pull_request]
    
    print(f"Found {len(open_issues)} open issues (excluding PRs)\n")
    
    checked_count = 0
    full_match_count = 0
    title_only_match_count = 0
    
    for issue in open_issues:
        # Skip if already labeled as "In OBIS"
        label_names = [label.name for label in issue.labels]
        if "In OBIS" in label_names:
            print(f"Skipping issue #{issue.number} (already labeled 'In OBIS')")
            continue
        
        # Double-check issue is actually open
        if issue.state != 'open':
            print(f"Skipping issue #{issue.number} (not open: {issue.state})")
            continue
        
        dataset_title = issue.title
        print(f"\n{'='*60}")
        print(f"Issue #{issue.number}: {dataset_title}")
        print(f"{'='*60}")
        
        # Extract URLs from issue body
        issue_urls = extract_urls_from_issue(issue.body)
        print(f"Found {len(issue_urls)} URLs in issue:")
        for u in issue_urls:
            print(f"  - {u}")
        
        # Search OBIS for exact match with URL verification
        title_match, url_match, dataset_url, obis_urls = search_obis_dataset(dataset_title, issue_urls)
        
        if title_match is True:
            print(f"\nOBIS Dataset: {dataset_url}")
            print(f"OBIS URLs found ({len(obis_urls)} total):")
            if obis_urls:
                for u in obis_urls:
                    print(f"  - {u}")
            else:
                print(f"  (No URLs found in OBIS dataset info)")
                            
            if url_match:
                # Full match - title and URL
                full_match_count += 1
                print(f"\n✓ FULL MATCH: Title and URL match!")
                
                if DRY_RUN:
                    print(f"\n[DRY RUN] Would add comment:")
                    print(f"  'Dataset is published to OBIS: {dataset_url}'")
                    print(f"[DRY RUN] Would add label: 'In OBIS'")
                    print(f"[DRY RUN] Would close issue")
                else:
                    # Check if we've already commented
                    existing_comments = [c for c in issue.get_comments() 
                                       if 'Dataset is published to OBIS:' in c.body]
                    
                    if not existing_comments:
                        comment_body = f"Dataset is published to OBIS: {dataset_url}"
                        issue.create_comment(comment_body)
                        print(f"\n✓ Added comment")
                    else:
                        print(f"\nℹ Already commented")
                    
                    # Add label
                    issue.add_to_labels("In OBIS")
                    print(f"✓ Added 'In OBIS' label")
                    
                    # Close the issue
                    issue.edit(state='closed')
                    print(f"✓ Closed issue")
            else:
                # Title match only - no URL match
                title_only_match_count += 1
                print(f"\n⚠ PARTIAL MATCH: Title matches but URLs don't match")
                
                if DRY_RUN:
                    print(f"\n[DRY RUN] Would add comment about title match but no URL match")
                    print(f"[DRY RUN] Would NOT add 'In OBIS' label")
                    print(f"[DRY RUN] Would NOT close issue")
                else:
                    # Check if we've already commented
                    existing_comments = [c for c in issue.get_comments() 
                                       if 'title matches a dataset in OBIS' in c.body]
                    
                    if not existing_comments:
                        comment_body = f"""⚠️ The title matches a dataset in OBIS, but the source URLs don't match:

**OBIS Dataset:** {dataset_url}

**Issue URLs:**
{chr(10).join(f'- {u}' for u in issue_urls)}

**OBIS URLs:**
{chr(10).join(f'- {u}' for u in obis_urls)}

Please verify if this is the same dataset or a different dataset with the same name."""
                        issue.create_comment(comment_body)
                        print(f"\n✓ Added warning comment")
                    else:
                        print(f"\nℹ Already commented")
        
        elif title_match is False:
            print(f"\n✗ No title match found in OBIS")
        else:
            print(f"\n⚠ Error checking OBIS")
        
        checked_count += 1
        
        # Rate limiting
        time.sleep(1)
    
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Checked: {checked_count} open issues")
    print(f"Full matches (title + URL): {full_match_count}")
    print(f"Partial matches (title only): {title_only_match_count}")
    if DRY_RUN:
        print(f"\n🔍 DRY RUN - No actual changes were made")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
