'''
给定工程代码，以一个.py为入口，每次运行都可以将一级的import的函数复制到一个文件中，用于代码混淆。因为代码混淆比如pyarmor这些，
都只会混淆一个.py文件的代码。

存在问题：
    不清楚为啥，经常性的出现相同代码和输入，两次执行的结果不一样！！！


改进1：
    添加功能，删除所有形式为''' '''和# 的注释。
    每次生成要判断代码中相同的import 代码，只保留一个，删除其余的。假如给deepseek源码让他改他无法修改，只能更针对性的让他修改，如下：
        假设我有['functools', 'timm.loss', 'cifar10.train_pytorch_base_DataSetSelect', 'deeplearning_relative.classify_img.convNeXt.convnext', 'torch', 'deeplearning_relative.classify_img.vit_pytorch_pretrained.model', 'deeplearning_relative.classify_img.vit_pytorch_pretrained.vision_transformer_dino', 'tools.utils', 'data_relative.imagenet_dataset.imagenet_data_loader', 'data_relative.imagenet_dataset.imgnet_dataloader_parameter', 'torch', 'time', 'argparse', 'pathlib', 'deeplearning_relative.classify_img.convNeXt.ArgsParserConvNeXt', 'deeplearning_relative.classify_img.convNeXt.datasets_original']这个list，用代码实现功能，删除掉相同的元素，只保留一个

'''
import os
import re
import sys
import ast
import importlib.util
import inspect
import time

# 定义标准库模块列表（简化版，实际应用中可以根据需要扩展）
builtin_modules = set([  # 假设这些是内建模块，可以根据实际情况扩展更多内建库
    'os', 'sys', 'math', 're', 'time', 'json', 'datetime', 'pickle', 'io', 'subprocess', 'ctypes', 'unittest', 'socket',
    'cv2', 'numpy', 'torch', "PIL", "datetime", "threading"])


def is_builtin(module_name, base_dir):
    """判断模块是否是内建模块或外部安装的模块"""
    # 如果模块名是内建模块，直接返回 True
    if module_name in builtin_modules or module_name in sys.builtin_module_names:
        return True

    # 获取模块的文件路径
    module_path = get_module_file_path(module_name, base_dir)

    # 如果找不到模块路径或模块路径不在项目目录下，视为外部库
    if module_path is None or not module_path.startswith(base_dir):
        return True

    return False


def normalize_code(code_str):
    def remove_docstrings(source_code):
        # 正则表达式模式匹配 '''...''' 或 """...""" 注释
        pattern = r"('''(.*?)'''|\"\"\"(.*?)\"\"\"|r'''(.*?)'''|r\"\"\"(.*?)\"\"\")"
        # 使用re.DOTALL标识使'.'可以匹配包括新行在内的所有字符
        result = re.sub(pattern, '', source_code, flags=re.DOTALL)
        return result

    code_str = remove_docstrings(code_str)
    normalized_lines = []
    current_line = ""
    linesOfSplit = code_str.split('\n')
    for line in linesOfSplit:
        line = re.split(" #", line)[0]  # 删除注释
        if line == "":  # 删除掉空行
            continue
        current_line += line + "\n"
    # 第一步：将多行代码合并为一行代码（处理换行符分割的代码）
    #     stripped_line = line.strip()
    #     if stripped_line.endswith('\\'):  # 处理多行语句的续行符
    #         current_line += stripped_line[:-1].strip() + ' '
    #     else:
    #         if current_line:  # 如果之前有未完成的行，则加上当前处理完的行
    #             normalized_lines.append(current_line + stripped_line)
    #             current_line = ""
    #         else:
    #             normalized_lines.append(stripped_line)
    # normalized_code = ' '.join(normalized_lines)
    #
    # # 第二步：找到所有import和from开头的代码，删除重复的，只保留一行
    # import_statements = set()
    # result_lines = []
    # for line in normalized_code.split(';'):  # 使用分号作为分隔符，因为现在的代码已经是一行了
    #     stripped_line = line.strip()
    #     if stripped_line.startswith(('import ', 'from ')):
    #         if stripped_line not in import_statements:
    #             import_statements.add(stripped_line)
    #             result_lines.append(stripped_line)
    #     else:
    #         result_lines.append(stripped_line)
    #
    # # 重新组合成字符串
    # final_code = '\n'.join(result_lines)
    return current_line


def get_module_file_path(module_name, base_dir):
    """通过模块名和基础目录路径获取模块的文件路径"""
    if module_name in builtin_modules or module_name in sys.builtin_module_names:
        return None

    # 尝试相对路径查找
    possible_paths = [
        os.path.join(base_dir, f"{module_name}.py"),
        os.path.join(base_dir, module_name.replace('.', os.sep) + '.py')
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    # 如果模块名没有找到，可能是一个已经安装的第三方包
    try:
        import importlib.util
        spec = importlib.util.find_spec(module_name)
        if spec and spec.origin:
            return spec.origin
    except ImportError:
        return None

    return None


def get_code_from_module(module_name, base_dir):
    """从模块获取源代码"""
    try:
        # 通过模块名获取该模块的源代码
        imp_file_path = get_module_file_path(module_name, base_dir)
        if imp_file_path:
            with open(imp_file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            # 如果模块是外部安装的，可以尝试使用 importlib
            module = importlib.import_module(module_name)
            source_code = inspect.getsource(module)
            return source_code
    except Exception as e:
        print(f"无法获取模块 {module_name} 的源代码: {e}")
        return None


def get_imports_from_file(file_path):
    """解析指定的 Python 文件，获取所有的 import 语句"""
    imports = []
    with open(file_path, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read(), filename=file_path)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module)

    imports1 = list(set(imports))
    return imports1


def deleteIfMainCode(strCode):
    useFullCode = re.split("if __name__", strCode)[0]
    return useFullCode


def deleteFirstMatchLineStr(inStr, template):
    # template = "model_dir=" # 要匹配的模板字符串
    # template = re.split(r"\.", template)[-1]

    # 将文本按行分割成列表
    lines = inStr.splitlines()

    # 查找包含模板的第一行
    for i, line in enumerate(lines):
        if template in line:
            if '\\' in lines[i]:
                del lines[i + 1]
            # 删除这一行
            del lines[i]
            break

    # 将列表重新组合成字符串
    modified_text = "\n".join(lines)
    return modified_text


# 修改 process_file 中对 is_builtin 的调用
def process_file(file_path, base_dir):
    """处理文件，将所有的非内建模块的 import 替换为其源代码"""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    code_before_main = ''.join(lines)  # 提取目标文件的代码
    code_before_main = normalize_code(code_before_main)
    imports = get_imports_from_file(file_path)

    # 用来替换的代码
    replaced_code = code_before_main
    for imp in imports:
        if not is_builtin(imp, base_dir):  # 传入 base_dir
            replaced_code = deleteFirstMatchLineStr(replaced_code, imp)

    for imp in imports:
        if not is_builtin(imp, base_dir):  # 传入 base_dir
            print(f"正在处理导入的模块：{imp}")
            # 获取模块源代码
            module_code = get_code_from_module(imp, base_dir)
            module_code = deleteIfMainCode(strCode=module_code)
            if module_code:
                replaced_code = module_code + replaced_code
    ifNoIntegrate = False
    if replaced_code == code_before_main:  # 假如代码没有任何更新了，就返回False
        ifNoIntegrate = True

    return replaced_code, ifNoIntegrate


def save_new_file(new_code, new_file_path):
    """保存修改后的代码到新文件"""
    with open(new_file_path, 'w', encoding='utf-8') as f:
        f.write(new_code)
    print(f"新文件已保存：{new_file_path}")


def process_project_file(project_dir, target_py, new_file_name="modified_code.py"):
    """处理项目中的 Python 文件，生成新的文件"""
    target_file_path = os.path.join(project_dir, target_py)

    # 检查文件是否存在
    if not os.path.exists(target_file_path):
        print(f"错误：文件 {target_py} 不存在。")
        return

    # 处理文件并获取替换后的代码
    new_code, ifNoIntegrate = process_file(target_file_path, project_dir)

    # 新文件的路径
    new_file_path = os.path.join(project_dir, new_file_name)
    # 保存新文件
    save_new_file(new_code, new_file_path)
    return ifNoIntegrate


def cycleRunProcess_project_file():
    project_directory = r'C:\Users\zhaoy\PycharmProjects\fun_code'  # 项目根目录
    # target_file = r'C:\Users\zhaoy\PycharmProjects\fun_code\serverMain.py'  # 需要处理的目标文件
    target_file = r"C:\Users\zhaoy\PycharmProjects\fun_code\deeplearning_relative\classify_img\convNeXt\trainConvNeXt_imgNetDataStruct.py"

    new_file_name = target_file[:-3] + "Integrated"

    process_project_file(project_directory, target_file, new_file_name + "0.py")
    for i in range(9999):
        time.sleep(4)
        ifNoIntegrate = process_project_file(project_directory, new_file_name + str(i) + ".py",
                                             new_file_name + str(i + 1) + ".py")
        if ifNoIntegrate:
            break
cycleRunProcess_project_file()
