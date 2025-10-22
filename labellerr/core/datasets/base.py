from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError
from labellerr.core.files import LabellerrFile
from labellerr import constants
import uuid
from abc import ABCMeta
import pprint

class LabellerrDataset:
    """
    Class for handling video dataset operations and fetching multiple video files.
    """
    
    def __init__(self, client: LabellerrClient, dataset_id: str, project_id: str):
        """
        Initialize video dataset instance.
        
        :param client: LabellerrClient instance
        :param dataset_id: Dataset ID
        :param project_id: Project ID containing the dataset
        """
        self.client = client
        self.dataset_id = dataset_id
        self.project_id = project_id
        self.client_id = client.client_id
    
    def fetch_files(self, page_size: int = 1000):
        """
        Fetch all video files in this dataset as LabellerrVideoFile instances.
        
        :param page_size: Number of files to fetch per API request (default: 10)
        :return: List of file IDs
        """
        try:
            all_file_ids = []
            next_search_after = None  # Start with None for first page
            
            while True:
                unique_id = str(uuid.uuid4())
                url = f"{constants.BASE_URL}/search/files/all"
                params = {
                    'sort_by': 'created_at',
                    'sort_order': 'desc',
                    'size': page_size,
                    'uuid': unique_id,
                    'dataset_id': self.dataset_id,
                    'client_id': self.client_id
                }
                
                # Add next_search_after only if it exists (don't send on first request)
                if next_search_after:
                    url+= f"?next_search_after={next_search_after}"
                
                # print(params)
                
                response = self.client.make_api_request(self.client_id, url, params, unique_id)
                
                # pprint.pprint(response)
                
                # Extract files from the response
                files = response.get('response', {}).get('files', [])
                
                # Collect file IDs
                for file_info in files:
                    file_id = file_info.get('file_id')
                    if file_id:
                        all_file_ids.append(file_id)
                
                # Get next_search_after for pagination
                next_search_after = response.get('response', {}).get('next_search_after')
                
                
                # Break if no more pages or no files returned
                if not next_search_after or not files:
                    break
                
                print(f"Fetched total: {len(all_file_ids)}")
            
            print(f"Total file IDs extracted: {len(all_file_ids)}")
            # return all_file_ids
            
            # Create LabellerrVideoFile instances for each file_id
            video_files = []
            print(f"\nCreating LabellerrFile instances for {len(all_file_ids)} files...")
            
            for file_id in all_file_ids:
                try:
                    video_file = LabellerrFile(
                        client=self.client,
                        file_id=file_id,
                        project_id=self.project_id,
                        dataset_id=self.dataset_id
                    )
                    video_files.append(video_file)
                except Exception as e:
                    print(f"Warning: Failed to create file instance for {file_id}: {str(e)}")
            
            print(f"Successfully created {len(video_files)} LabellerrFile instances")
            return video_files
        
        except Exception as e:
            raise LabellerrError(f"Failed to fetch dataset files: {str(e)}")
    
    def download(self):
        """
        Process all video files in the dataset: download frames, create videos, 
        and automatically clean up temporary files.
        
        :param output_folder: Base folder where dataset folder will be created
        :return: List of processing results for all files
        """
        try:
            print(f"\n{'#'*70}")
            print(f"# Starting batch video processing for dataset: {self.dataset_id}")
            print(f"{'#'*70}\n")
            
            # Fetch all video files
            video_files = self.fetch_files()
            
            if not video_files:
                print("No video files found in dataset")
                return []
            
            print(f"\nProcessing {len(video_files)} video files...\n")
            
            results = []
            successful = 0
            failed = 0
            
            print(f"\nStarting download of {len(video_files)} files...")
            for idx, video_file in enumerate(video_files, 1):
                try:
                    # Call the new all-in-one method
                    result = video_file.download_create_video_auto_cleanup()
                    results.append(result)
                    successful += 1
                    print(f"\rFiles processed: {idx}/{len(video_files)} ({successful} successful, {failed} failed)", end="", flush=True)
                    
                except Exception as e:
                    error_result = {
                        'status': 'failed',
                        'file_id': video_file.file_id,
                        'error': str(e)
                    }
                    results.append(error_result)
                    failed += 1
                    print(f"\rFiles processed: {idx}/{len(video_files)} ({successful} successful, {failed} failed)", end="", flush=True)
            
            # Summary
            print(f"\n{'#'*70}")
            print(f"# Batch Processing Complete")
            print(f"# Total files: {len(video_files)}")
            print(f"# Successful: {successful}")
            print(f"# Failed: {failed}")
            print(f"{'#'*70}\n")
            
            return results
                
        except Exception as e:
            raise LabellerrError(f"Failed to process dataset videos: {str(e)}")


# if __name__ == "__main__":
#     # Example usage
#     api_key = ""
#     api_secret = ""
#     client_id = ""
    
#     dataset_id = "59438ec3-12e0-4687-8847-1e6e01b0bf25"
#     project_id = "farrah_supposed_hookworm_34155"
    
#     client = LabellerrClient(api_key, api_secret, client_id)
    
#     dataset = LabellerrVideoDataset(client, dataset_id, project_id)
    
#     # Process all videos in the dataset
#     results = dataset.download()
    
#     # Print summary
#     pprint.pprint(results)