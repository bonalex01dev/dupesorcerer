import hashlib
import math


def calculate_sha256(filepath, buffer_size=65536):
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                sha256_hash.update(data)
        return sha256_hash.hexdigest()
    except IOError as e:
        print(f"Error hashing file {filepath}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error hashing file {filepath}: {e}")
        return None


def format_size(size_bytes):
    if size_bytes is None or size_bytes < 0:
        return "N/A"
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    try:
        i = int(math.floor(math.log(size_bytes, 1024)))
        if i >= len(size_name):
            i = len(size_name) - 1
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"
    except ValueError:
        return "Invalid Size"
    except Exception:
        return "Error Size"


def clear_layout(layout):
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout is not None:
                    clear_layout(sub_layout)
