"""
Decompress and compress map .entities files.
Requires oo2core_8_win64.dll (windows) or liblinoodle.so (linux) to be in the
same folder.

Original code by Pizzaandy
"""
import sys
import os
import ctypes

from argparse import ArgumentParser


class Oodle:
    def __init__(self):
        if 'linux' in sys.platform:
            self.oodle_path = './liblinoodle.so'
        else:
            self.oodle_path = './oo2core_8_win64.dll'

    def is_compressed(self, file_path:str) -> bool:
        with open(file_path, "rb") as file:
            file.seek(0x0)
            file.seek(0x8)
            compressed_size = int.from_bytes(file.read(8), "little")
            file.seek(0x10)
            bytes_data = file.read()
            if len(bytes_data) == compressed_size:
                return True
            
            return False
    
    def decompress(self, file_path:str) -> str:
        if not self.is_compressed(file_path):
            raise Exception('File is not compressed')
        
        with open(file_path, 'rb') as f:
            f.seek(0x0)
            size_uncompressed = int.from_bytes(f.read(8), 'little')
            f.seek(0x8)
            size_compressed = int.from_bytes(f.read(8), 'little')
            f.seek(0x10)
            data = f.read()
        if len(data) != size_compressed:
            raise Exception('Size in header not equal to size of data')
        
        buffer_compressed = ctypes.create_string_buffer(data)
        data_compressed = ctypes.cast(buffer_compressed,
                                      ctypes.POINTER(ctypes.c_ubyte))
        buffer_decompressed = \
            ctypes.create_string_buffer(size_uncompressed)
        data_decompressed = ctypes.cast(buffer_decompressed,
                                        ctypes.POINTER(ctypes.c_ubyte))

        try:
            oodlz_decompress = \
                ctypes.cdll[self.oodle_path]["OodleLZ_Decompress"]
        except OSError:
            raise FileNotFoundError(
                f"{self.oodle_path[2:]} not in folder!")
        
        oodlz_decompress.restype = ctypes.c_int
        oodlz_decompress.argtypes = [
            ctypes.POINTER(ctypes.c_ubyte),  # src_buf
            ctypes.c_int,  # src_len
            ctypes.POINTER(ctypes.c_ubyte),  # dst
            ctypes.c_size_t,  # dst_size
            ctypes.c_int,  # fuzz
            ctypes.c_int,  # crc
            ctypes.c_int,  # verbose
            ctypes.POINTER(ctypes.c_ubyte),  # dst_base
            ctypes.c_size_t,  # e
            ctypes.c_void_p,  # cb
            ctypes.c_void_p,  # cb_ctx
            ctypes.c_void_p,  # scratch
            ctypes.c_size_t,  # scratch_size
            ctypes.c_int,  # threadPhase
        ]

        if ret := oodlz_decompress(data_compressed, size_compressed,
                                   data_decompressed,
                                   ctypes.c_size_t(size_uncompressed),
                                   1, 1, 0, None, 0, None, None, None,
                                   0, 0) != size_uncompressed:
            raise Exception(f'expected size of {size_uncompressed},'
                            f'got "{ret}" :(')
        return ctypes.string_at(buffer_decompressed).decode()

    def decompress_to_file(self, file_path:str, dest_file_path:str) -> None:
        data = self.decompress(file_path)

        with open(dest_file_path, 'w+', newline='\n') as f:
            f.write(data)
        
        print(f'decompressed {file_path} to {dest_file_path}')
    
    def compress_to_file(self, file_path:str, dest_file_path:str) -> None:
        if self.is_compressed(file_path):
            raise Exception('File is already compressed')

        size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            decompressed_buf = ctypes.create_string_buffer(f.read(), size)
        decompressed_data = ctypes.cast(decompressed_buf,
                                        ctypes.POINTER(ctypes.c_ubyte))

        try:
            compressed_buf = ctypes.create_string_buffer(size + 65536)  # magic number?
        except MemoryError:
            raise MemoryError("Couldn't allocate memory for compression")
        compressed_data = ctypes.cast(compressed_buf,
                                      ctypes.POINTER(ctypes.c_ubyte))

        try:
            oodlz_compress = \
                ctypes.cdll[self.oodle_path]["OodleLZ_Compress"]
        except OSError:
            raise FileNotFoundError(f"{self.oodle_path[2:]} not in folder!")

        oodlz_compress.restype = ctypes.c_int
        oodlz_compress.argtypes = [
            ctypes.c_int,  # codec
            ctypes.POINTER(ctypes.c_ubyte),  # src_buf
            ctypes.c_size_t,  # src_len
            ctypes.POINTER(ctypes.c_ubyte),  # dst
            ctypes.c_int,  # level
            ctypes.c_void_p,  # opts
            ctypes.c_size_t,  # offs
            ctypes.c_size_t,  # unused
            ctypes.c_void_p,  # scratch
            ctypes.c_size_t,  # scratch_size
        ]

        compressed_size = oodlz_compress(13, decompressed_data,
            ctypes.c_size_t(size), compressed_data, 4, 0, 0, 0, 0, 0)

        if compressed_size < 0:
            raise Exception(f'{compressed_size} is negative, '
                            f'compression failed!')

        with open(dest_file_path, "wb") as f:
            f.write(size.to_bytes(8, "little"))
            f.write(compressed_size.to_bytes(8, "little"))
            f.write(compressed_buf[0:compressed_size])

        print(f"Compressed {file_path} to {dest_file_path}")


if __name__ == '__main__':
    ap = ArgumentParser(description='Compress or decompress files.')

    ap.add_argument('-c', '--compress', action='store_true',
        help='Compress the source file to destination file')
    ap.add_argument('-d', '--decompress', action='store_true',
        help='Decompress the source file to destination file')
    ap.add_argument('source', type=str,
        help='The source file')
    ap.add_argument('destination', type=str,
        help='The destination file')

    args = ap.parse_args()

    if args.compress == args.decompress:
        print('You must specify either -c (compress) or -d '
              '(decompress).')
        sys.exit()

    oodle = Oodle()
    if args.compress:
        oodle.compress_to_file(args.source, args.destination)
    else:
        oodle.decompress_to_file(args.source, args.destination)

    