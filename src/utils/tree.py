# coding=utf-8
# (C) Copyright 2022 Jindřich Šestak (xsesta05)
# Licenced under MIT.
# Part of diploma thesis.
# Content: File with tree representation of the mesh.

import json


class TreeNode(object):
    def __init__(self, data, parent):
        self.data = data
        self.parent = parent
        self.children = []

    def add_child(self, obj):
        self.children.append(obj)

    def del_child(self, obj):
        self.children.remove(obj)

    def get_routes(self):
        dic = {}
        for i in self.children:
            descendants = [i.data]
            descendants.extend(i.get_all())
            for d in descendants:
                dic[d] = i.data
        return dic

    def get_all(self):
        al = []
        for i in self.children:
            al.append(i.data)
            al.extend(i.get_all())
        return al

    def __str__(self, level=0):
        ret = "\t" * level + repr(self.data) + "\n"
        for child in self.children:
            ret += child.__str__(level + 1)
        return ret

    def pack(self):
        return {"node": str(self.data), "child": [child.pack() for child in self.children]}


class Tree:
    def __init__(self):
        self.root = TreeNode('ROOT', None)

    def __str__(self):
        return self.root.__str__()

    def pack(self):
        return self.root.pack()

    def search(self, node_id, actual_node=None):
        if actual_node is None:
            actual_node = self.root
        if actual_node is None or actual_node.data == node_id:
            return actual_node
        for c in actual_node.children:
            if self.search(node_id, c):
                return self.search(node_id, c)

    def del_node(self, node_id):
        if not self.root:
            return False
        failed_node = self.search(node_id)
        parent = failed_node.parent
        parent.del_child(failed_node)


def get_all_nodes(dict_var):
    for k, v in dict_var.items():
        if k == "node":
            yield v
        elif isinstance(v, dict):
            for id_val in get_all_nodes(v):
                yield id_val
        elif isinstance(v, list):
            for item in v:
                yield from get_all_nodes(item)


def json_to_tree(dict_var, tree, node):
    n = None
    for k, v in dict_var.items():
        if k == "node":
            if not node:
                n = TreeNode(v, None)
                tree.root = n
            else:
                n = TreeNode(v, node)
                node.add_child(n)
        elif isinstance(v, list):
            for item in v:
                json_to_tree(item, tree, n)


def main():
    tmp = {"node": "3c:71:bb:e4:8b:89",
           "child":
               [
                   {"node": "3c:71:bb:e4:8b:a1",
                    "child":
                        [
                            {
                                "node": "3c:71:bb:e4:8b:b9",
                                "child": [
                                    {"node": "3c:71:bb:e4:8b:a2",
                                     "child": []
                                     }
                                ]
                            },

                            {
                                "node": "3c:71:bb:e4:8b:11",
                                "child": [
                                    {"node": "3c:71:bb:e4:8b:42",
                                     "child": []
                                     }
                                ]
                            }
                        ]
                    },
                   {
                       "node": "3c:71:bb:e4:8b:d5",
                       "child": [
                           {"node": "3c:71:bb:e4:8b:d6",
                            "child": []
                            }
                       ]
                   },
               ]
           }

    all_nodes = get_all_nodes(tmp)
    # for i in all_nodes:
    #     print(i)
    tree = Tree()
    json_to_tree(tmp, tree, None)
    print(" TREE: ", tree)
    # print(tree.root._get_descendants())
    # print(tree.root.get_routes())
    print(tree.root.get_all())
    # for i in get_all_nodes(tree.pack()):
    #     print(i)


if __name__ == "__main__":
    main()
