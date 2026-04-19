# Internal filename: <string>
# Bytecode version: 3.9.0beta5 (201)
# AoV Tools 3.5.0
# Source timestamp: 2020-11-01 16:18:20  UTC (1630640118)

import os
import struct
import xml.etree.ElementTree as ET
from xml.dom import minidom


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BYTES_DIR = os.path.join(BASE_DIR, "bytes")
XML_DIR = os.path.join(BASE_DIR, "xml")

os.makedirs(BYTES_DIR, exist_ok=True)
os.makedirs(XML_DIR, exist_ok=True)


RESET = "\033[0m"
GREEN_GLOW = "\033[1;92m"
RED_GLOW = "\033[1;91m"

def log_info(msg):
    print(f"[{GREEN_GLOW}INFO{RESET}] {msg}")

def log_error(msg):
    print(f"[{RED_GLOW}ERROR{RESET}] {msg}")


def byteint(i):
    return struct.pack("<I", i)

def indent(elem, level=0):
    i = "\n" + level * "    "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "    "
        for e in elem:
            indent(e, level + 1)
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


class BinaryParser:
    def __init__(self, filepath):
        self.filepath = filepath
        self.byt = open(filepath, "rb")
        self.root = None

    def read_int(self):
        return int.from_bytes(self.byt.read(4), "little")

    def read_string(self):
        length = self.read_int()
        return self.byt.read(length - 4).decode("utf-8", errors="ignore")

    def read_attribute(self):
        pos = self.byt.tell()
        offset = self.read_int()
        attr_type = self.read_int()

        data = self.byt.read(offset - 8).decode("utf-8", errors="ignore")
        self.byt.seek(pos + offset, 0)

        if attr_type == 5:
            return data[1:]
        elif attr_type == 6:
            return {"Var": data.replace("JT", "")}
        elif attr_type == 8:
            return {"Type": data.replace("Type", "")}
        else:
            return {str(attr_type): data}

    def parse_node(self):
        node_size = self.read_int()
        start = self.byt.tell()

        tag = self.read_string()
        if tag == "Element":
            tag = "Item"

        node = ET.Element(tag)

        self.read_int()
        attr_count = self.read_int()

        for _ in range(attr_count):
            attr = self.read_attribute()
            if isinstance(attr, str):
                node.text = attr
            else:
                node.attrib.update(attr)

        self.read_int()

        child_block = self.read_int()
        if child_block and child_block > 4:
            child_count = self.read_int()
            for _ in range(child_count):
                child = self.parse_node()
                node.append(child)

        self.byt.seek(start + node_size - 4)
        return node

    def parse(self):
        self.root = self.parse_node()

    def save(self, output_path):
        xml_str = minidom.parseString(
            ET.tostring(self.root)
        ).toprettyxml(indent="    ")

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(xml_str)

    def close(self):
        self.byt.close()


def fix_actor_name(elem):
    if elem.tag == "ActorName" and elem.text == "WhiteBox":
        elem.text = "WhiteBox_XML_BY_MICKEY_"
    for c in elem:
        fix_actor_name(c)


def mode_bytes_to_xml():
    for root_dir, _, files in os.walk(BYTES_DIR):
        for file in files:
            if not file.endswith(".bytes"):
                continue
            try:
                input_path = os.path.join(root_dir, file)

                relative = os.path.relpath(input_path, BYTES_DIR)
                output_path = os.path.join(
                    XML_DIR, relative.replace(".bytes", ".xml")
                )

                parser = BinaryParser(input_path)
                parser.parse()
                fix_actor_name(parser.root)
                parser.save(output_path)
                parser.close()

                log_info(f"{relative} -> xml")
            except Exception as e:
                log_error(f"{file} ({e})")


def bytestr(s):
    return byteint(len(s) + 4) + s.encode()

def byteattr(key, attr):
    if key == "Var":
        aid = 6
        s = "JT" + attr[key]
    elif key == "Type":
        aid = 8
        s = "Type" + attr[key]
    else:
        aid = int(key)
        s = attr[key]
    b = s.encode()
    return byteint(len(b) + 8) + byteint(aid) + b

def bytenode(node):
    name = "Element" if node.tag == "Item" else node.tag
    data = bytestr(name)

    attr_data = b""
    count = len(node.attrib)

    for k in node.attrib:
        attr_data += byteattr(k, node.attrib)

    if node.text and node.text.strip():
        v = ("V" + node.text).encode()
        attr_data += byteint(len(v) + 8) + byteint(5) + v
        count += 1

    attr_block = byteint(len(attr_data) + 8) + byteint(count) + attr_data + byteint(4)

    child_data = b""
    if len(node):
        for c in node:
            child_data += bytenode(c)
        child_data = byteint(len(child_data) + 8) + byteint(len(node)) + child_data
    else:
        child_data = byteint(4)

    body = data + attr_block + child_data
    return byteint(len(body) + 4) + body


def mode_xml_to_bytes():
    for root_dir, _, files in os.walk(XML_DIR):
        for file in files:
            if not file.endswith(".xml"):
                continue
            try:
                input_path = os.path.join(root_dir, file)

                relative = os.path.relpath(input_path, XML_DIR)
                output_path = os.path.join(
                    BYTES_DIR, relative.replace(".xml", ".bytes")
                )

                os.makedirs(os.path.dirname(output_path), exist_ok=True)

                tree = ET.parse(input_path)
                byt = bytenode(tree.getroot())

                with open(output_path, "wb") as f:
                    f.write(byt)

                log_info(f"{relative} -> bytes")
            except Exception as e:
                log_error(f"{file} ({e})")


while True:
    print("\n[INFO] 1: Bytes -> XML")
    print("[INFO] 2: XML -> Bytes")
    print("[INFO] 0: Exit")

    mode = input("[เลือก]: ").strip()

    if mode == "1":
        mode_bytes_to_xml()
    elif mode == "2":
        mode_xml_to_bytes()
    elif mode == "0":
        break
    else:
        log_error("โหมดไม่ถูกต้อง")

    while True:
        ans = input("\n[INFO] ทำงานใหม่หรือไม่? y/n : ").strip().lower()
        if ans == "y":
            break
        elif ans == "n":
            exit()
        else:
            print("กรุณาใส่ y หรือ n เท่านั้น")