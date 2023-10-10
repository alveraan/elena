import importlib

def check_requirements():
    try:
        with open('requirements.txt', 'r') as f:
            for line in f:
                package = line.strip().split('==')[0]
                importlib.import_module(package)
    except ImportError as e:
        print(f"[ERROR] Missing package: {e.name}")
        return 1
    except Exception as e:
        print(f"[ERROR] An error occurred: {e}")
        return 2
    return 0

if __name__ == "__main__":
    exit_code = check_requirements()
    exit(exit_code)