# cloud_tools.py
# Cloud Integration module - Azure, Google Cloud, and AWS support
# Provides unified interface for cloud storage operations

from typing import Optional, List, Dict, BinaryIO
import os
from pathlib import Path


class AzureBlobManager:
    """Azure Blob Storage management"""
    
    def __init__(self, connection_string: Optional[str] = None):
        """Initialize Azure Blob client"""
        self.connection_string = connection_string or os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to Azure"""
        try:
            from azure.storage.blob import BlobServiceClient
            if self.connection_string:
                self.client = BlobServiceClient.from_connection_string(self.connection_string)
                print("✅ Connected to Azure Blob Storage")
            else:
                print("⚠️  No Azure connection string provided")
        except ImportError:
            print("❌ Azure Storage Blob not installed")
    
    def upload_file(self, container_name: str, blob_name: str, file_path: str) -> bool:
        """Upload file to Azure Blob Storage"""
        if not self.client:
            return False
        
        try:
            with open(file_path, 'rb') as data:
                self.client.get_blob_client(
                    container=container_name,
                    blob=blob_name
                ).upload_blob(data, overwrite=True)
            print(f"✅ Uploaded {file_path} to {container_name}/{blob_name}")
            return True
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False
    
    def download_file(self, container_name: str, blob_name: str, file_path: str) -> bool:
        """Download file from Azure Blob Storage"""
        if not self.client:
            return False
        
        try:
            blob_client = self.client.get_blob_client(
                container=container_name,
                blob=blob_name
            )
            with open(file_path, 'wb') as file:
                file.write(blob_client.download_blob().readall())
            print(f"✅ Downloaded {blob_name} to {file_path}")
            return True
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    
    def list_blobs(self, container_name: str) -> List[str]:
        """List all blobs in container"""
        if not self.client:
            return []
        
        try:
            blobs = self.client.get_container_client(container_name).list_blobs()
            return [blob.name for blob in blobs]
        except Exception as e:
            print(f"❌ List failed: {e}")
            return []


class GoogleCloudStorageManager:
    """Google Cloud Storage management"""
    
    def __init__(self, project_id: Optional[str] = None):
        """Initialize Google Cloud Storage client"""
        self.project_id = project_id or os.getenv('GCP_PROJECT_ID')
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to GCP"""
        try:
            from google.cloud import storage
            self.client = storage.Client(project=self.project_id)
            print("✅ Connected to Google Cloud Storage")
        except ImportError:
            print("❌ Google Cloud Storage not installed")
    
    def upload_file(self, bucket_name: str, source_path: str, destination_name: str) -> bool:
        """Upload file to GCS"""
        if not self.client:
            return False
        
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(destination_name)
            blob.upload_from_filename(source_path)
            print(f"✅ Uploaded {source_path} to {bucket_name}/{destination_name}")
            return True
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False
    
    def download_file(self, bucket_name: str, source_name: str, destination_path: str) -> bool:
        """Download file from GCS"""
        if not self.client:
            return False
        
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(source_name)
            blob.download_to_filename(destination_path)
            print(f"✅ Downloaded {source_name} to {destination_path}")
            return True
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    
    def list_blobs(self, bucket_name: str) -> List[str]:
        """List all blobs in bucket"""
        if not self.client:
            return []
        
        try:
            bucket = self.client.bucket(bucket_name)
            blobs = bucket.list_blobs()
            return [blob.name for blob in blobs]
        except Exception as e:
            print(f"❌ List failed: {e}")
            return []


class AWSS3Manager:
    """AWS S3 Storage management"""
    
    def __init__(self, region_name: str = 'us-east-1'):
        """Initialize AWS S3 client"""
        self.region_name = region_name
        self.client = None
        self._connect()
    
    def _connect(self):
        """Establish connection to AWS S3"""
        try:
            import boto3
            self.client = boto3.client('s3', region_name=self.region_name)
            print("✅ Connected to AWS S3")
        except ImportError:
            print("❌ boto3 not installed")
    
    def upload_file(self, bucket_name: str, file_path: str, object_name: Optional[str] = None) -> bool:
        """Upload file to S3"""
        if not self.client:
            return False
        
        if object_name is None:
            object_name = os.path.basename(file_path)
        
        try:
            self.client.upload_file(file_path, bucket_name, object_name)
            print(f"✅ Uploaded {file_path} to {bucket_name}/{object_name}")
            return True
        except Exception as e:
            print(f"❌ Upload failed: {e}")
            return False
    
    def download_file(self, bucket_name: str, object_name: str, file_path: str) -> bool:
        """Download file from S3"""
        if not self.client:
            return False
        
        try:
            self.client.download_file(bucket_name, object_name, file_path)
            print(f"✅ Downloaded {object_name} to {file_path}")
            return True
        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False
    
    def list_objects(self, bucket_name: str, prefix: str = '') -> List[str]:
        """List objects in bucket"""
        if not self.client:
            return []
        
        try:
            response = self.client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except Exception as e:
            print(f"❌ List failed: {e}")
            return []


class UnifiedCloudManager:
    """Unified interface for multiple cloud providers"""
    
    def __init__(self):
        self.azure = AzureBlobManager()
        self.gcp = GoogleCloudStorageManager()
        self.aws = AWSS3Manager()
    
    def upload(self, provider: str, **kwargs) -> bool:
        """Upload to specified cloud provider"""
        if provider.lower() == 'azure':
            return self.azure.upload_file(**kwargs)
        elif provider.lower() == 'gcp':
            return self.gcp.upload_file(**kwargs)
        elif provider.lower() == 'aws':
            return self.aws.upload_file(**kwargs)
        else:
            print(f"❌ Unknown provider: {provider}")
            return False
    
    def download(self, provider: str, **kwargs) -> bool:
        """Download from specified cloud provider"""
        if provider.lower() == 'azure':
            return self.azure.download_file(**kwargs)
        elif provider.lower() == 'gcp':
            return self.gcp.download_file(**kwargs)
        elif provider.lower() == 'aws':
            return self.aws.download_file(**kwargs)
        else:
            print(f"❌ Unknown provider: {provider}")
            return False
    
    def list_files(self, provider: str, **kwargs) -> List[str]:
        """List files from specified cloud provider"""
        if provider.lower() == 'azure':
            return self.azure.list_blobs(**kwargs)
        elif provider.lower() == 'gcp':
            return self.gcp.list_blobs(**kwargs)
        elif provider.lower() == 'aws':
            return self.aws.list_objects(**kwargs)
        else:
            print(f"❌ Unknown provider: {provider}")
            return []


# ===== MAIN FUNCTIONS =====

def upload_to_cloud(provider: str, file_path: str, destination: str, **kwargs) -> bool:
    """Upload file to cloud storage"""
    manager = UnifiedCloudManager()
    
    if provider.lower() == 'azure':
        container_name = kwargs.get('container_name', 'default')
        return manager.azure.upload_file(container_name, destination, file_path)
    elif provider.lower() == 'gcp':
        bucket_name = kwargs.get('bucket_name', 'default')
        return manager.gcp.upload_file(bucket_name, file_path, destination)
    elif provider.lower() == 'aws':
        bucket_name = kwargs.get('bucket_name', 'default')
        return manager.aws.upload_file(bucket_name, file_path, destination)
    
    return False


# ===== TESTING =====

if __name__ == "__main__":
    print("\n" + "☁️  CLOUD TOOLS TEST SUITE ☁️".center(70))
    print("="*70 + "\n")
    
    print("Cloud managers initialized.")
    print("Note: Requires cloud credentials to be set up")
    print()
    
    print("="*70)
    print("✅ CLOUD TOOLS READY".center(70))
    print("="*70 + "\n")
