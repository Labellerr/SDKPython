from labellerr.client import LabellerrClient
from labellerr.exceptions import LabellerrError
from labellerr import constants
import uuid
from abc import ABCMeta


class LabellerrFileMeta(ABCMeta):
    """Metaclass that combines ABC functionality with factory pattern"""
    
    _registry = {}
    
    @classmethod
    def register(cls, data_type, file_class):
        """Register a file type handler"""
        cls._registry[data_type.lower()] = file_class
    
    
    def __call__(cls, client, file_id, project_id, dataset_id = None, **kwargs):
        
        if cls.__name__ != 'LabellerrFile':
            
            instance = cls.__new__(cls)
            if isinstance(instance, cls):
                instance.__init__(client, file_id, project_id, dataset_id=dataset_id, **kwargs)
            return instance
        
        
        try:
            unique_id = str(uuid.uuid4())
            client_id = client.client_id
            params = {
                'file_id': file_id,
                'include_answers': 'false',
                'project_id': project_id,
                'uuid': unique_id,
                'client_id': client_id
            }
            
            # TODO: Add dataset_id to params based on precedence logic
            # Priority: project_id > dataset_id
            
            url = f"{constants.BASE_URL}/data/file_data"
            response = client.make_api_request(client_id, url, params, unique_id)
            
            # Extract data_type from response
            file_metadata = response.get('file_metadata', {})
            data_type = response.get('data_type', '').lower()
            
            # print(f"Detected file type: {data_type}")
            
            file_class = cls._registry.get(data_type)
            if file_class is None:
                raise LabellerrError(f"Unsupported file type: {data_type}")
            
            return file_class(client, file_id, project_id, dataset_id=dataset_id, file_metadata=file_metadata)
            
        except Exception as e:
            raise LabellerrError(f"Failed to create file instance: {str(e)}")


            
            # # Route to appropriate subclass
            # if data_type == 'image':
            #     return LabellerrImageFile(client, file_id, project_id, dataset_id=dataset_id, 
            #                              file_metadata=file_metadata)
            # elif data_type == 'video':
            #     return LabellerrVideoFile(client, file_id, project_id, dataset_id=dataset_id,
            #                              file_metadata=file_metadata)
            # else:
            #     raise LabellerrError(f"Unsupported file type: {data_type}")

                
        # except Exception as e:
        #     raise LabellerrError(f"Failed to create file instance: {str(e)}")


class LabellerrFile(metaclass=LabellerrFileMeta):
    """Base class for all Labellerr files with factory behavior"""
    
    def __init__(self, client: LabellerrClient, file_id: str, project_id: str,
                  dataset_id: str | None = None, **kwargs):
        """
        Initialize base file attributes
        
        :param client: LabellerrClient instance
        :param file_id: Unique file identifier
        :param project_id: Project ID containing the file
        :param dataset_id: Optional dataset ID
        :param kwargs: Additional file data (file_metadata, response, etc.)
        """
        self.client = client
        self.file_id = file_id
        self.project_id = project_id
        self.client_id = client.client_id
        self.dataset_id = dataset_id
        
        # Store metadata from factory creation
        self.metadata = kwargs.get('file_metadata', {})

        
    def get_metadata(self, include_answers: bool = False):
        """
        Refresh and retrieve file metadata from Labellerr API.
        
        :param include_answers: Whether to include annotation answers
        :return: Dictionary containing file metadata
        """
        try:
            unique_id = str(uuid.uuid4())
            
            params = {
                'file_id': self.file_id,
                'include_answers': str(include_answers).lower(),
                'project_id': self.project_id,
                'uuid': unique_id,
                'client_id': self.client_id
            }
            
            # TODO: Add dataset_id handling if needed
            
            url = f"{constants.BASE_URL}/data/file_data"
            response = self.client.make_api_request(self.client_id, url, params, unique_id)
            
            # Update cached metadata
            self.metadata = response.get('file_metadata', {})
            
            return response
                    
        except Exception as e:
            raise LabellerrError(f"Failed to fetch file metadata: {str(e)}")
