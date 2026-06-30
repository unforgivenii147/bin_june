#!/data/data/com.termux/files/usr/bin/python


from pathlib import Path
import os
import multiprocessing
import json
import argparse

python


def load_json_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                return [data]
    except json.JSONDecodeError as e:
        print(f"Ошибка декодирования JSON в файле {file_path}: {e}")
        return []
    except Exception as e:
        print(f"Произошла ошибка при чтении файла {file_path}: {e}")
        return []


def merge_json_files(input_paths):
    json_files = []
    for path_str in input_paths:
        path = Path(path_str)
        if path.is_file() and path.suffix == ".json":
            json_files.append(path)
        elif path.is_dir():
            for file in path.rglob("*.json"):
                json_files.append(file)
        else:
            print(f"Предупреждение: Путь '{path_str}' не является файлом .json или директорией. Пропускается.")
    if not json_files:
        print("Не найдено JSON-файлов для объединения.")
        return []
    print(f"Найдено {len(json_files)} JSON-файлов для обработки.")
    with multiprocessing.Pool(os.cpu_count()) as pool:
        list_of_data_lists = pool.map(load_json_file, json_files)
    merged_data = []
    for data_list in list_of_data_lists:
        merged_data.extend(data_list)
    return merged_data


def main():
    parser = argparse.ArgumentParser(description="Объединение JSON-файлов.")
    parser.add_argument(
        "input_paths",
        nargs="*",
        help="Пути к файлам или директориям для обработки. Если не указаны, обрабатывается текущая директория.",
    )
    parser.add_argument(
        "--output", "-o", default="mergedf.json", help="Имя выходного файла. По умолчанию 'mergedf.json'."
    )
    args = parser.parse_args()
    if not args.input_paths:
        input_paths_to_process = ["."]
    else:
        input_paths_to_process = args.input_paths
    merged_result = merge_json_files(input_paths_to_process)
    if merged_result:
        output_file_path = Path(args.output)
        if output_file_path.exists():
            print(f"Предупреждение: Выходной файл '{output_file_path}' уже существует. Перезаписываю.")
        try:
            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(merged_result, f, ensure_ascii=False, indent=4)
            print(f"Все JSON-файлы успешно объединены в '{output_file_path}'.")
        except Exception as e:
            print(f"Ошибка при записи объединенных данных в файл '{output_file_path}': {e}")
    else:
        print("There is no data to write to the output file.")


if __name__ == "__main__":
    main()
