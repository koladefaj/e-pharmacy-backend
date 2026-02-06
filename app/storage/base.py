from abc import ABC, abstractmethod


class StorageInterface(ABC):

    @abstractmethod
    def generate_presigned_url():
        pass

    @abstractmethod
    async def upload():
        pass

    @abstractmethod
    async def get_file_path():
        pass
