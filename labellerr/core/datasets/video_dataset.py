from ..exceptions import LabellerrError
from ..schemas import DatasetDataType
from .base import LabellerrDataset, LabellerrDatasetMeta


class VideoDataset(LabellerrDataset):
    """
    Class for handling video dataset operations and fetching multiple video files.
    """

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
                    print(
                        f"\rFiles processed: {idx}/{len(video_files)} ({successful} successful, {failed} failed)",
                        end="",
                        flush=True,
                    )

                except Exception as e:
                    error_result = {
                        "status": "failed",
                        "file_id": video_file.file_id,
                        "error": str(e),
                    }
                    results.append(error_result)
                    failed += 1
                    print(
                        f"\rFiles processed: {idx}/{len(video_files)} ({successful} successful, {failed} failed)",
                        end="",
                        flush=True,
                    )

            # Summary
            print(f"\n{'#'*70}")
            print("# Batch Processing Complete")
            print(f"# Total files: {len(video_files)}")
            print(f"# Successful: {successful}")
            print(f"# Failed: {failed}")
            print(f"{'#'*70}\n")

            return results

        except Exception as e:
            raise LabellerrError(f"Failed to process dataset videos: {str(e)}")


LabellerrDatasetMeta._register(DatasetDataType.video, VideoDataset)
