# coding=utf-8
# (C) Copyright 2022 Jindrich Sestak (xsesta05)
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

    def get_children(self):
        dic = {}
        for i in self.children:
            descentants = i._get_descendants()
            if not isinstance(descentants, list):
                descentants = [descentants]
            for d in descentants:
                dic[d] = i.data
        return dic

    def _get_descendants(self):
        if self.children:
            return [self.data] + [child._get_descendants() for child in self.children]
            # for child in self.children:
            #     yield from child._get_descendants()
        else:
            return self.data

    def __str__(self, level=0):
        ret = "\t"*level+repr(self.data)+"\n"
        for child in self.children:
            ret += child.__str__(level+1)
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

    def search(self, node_id, actual_node = None):
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


def create_tree(dic, tree, node):
    """
    Creates a tree from nested dict.
    """
    if not tree:
        tree = Tree()
    n = 0
    for k, v in dic.items():
        if k == "node":
            if node:
                n = TreeNode(v, node)
                node.add_child(n)
            else :
                n = TreeNode(v, None)
                tree.root = n
        elif isinstance(v, dict) and n:
            n = create_tree(v, tree, n)
        else:
            n = create_tree(v, tree, node)
    return n

def treeify(data) -> dict:
    """
    Make nested dict from JSON data. Viz. https://stackoverflow.com/questions/55926688/python-create-tree-from-a-json-file
    """
    if isinstance(data, dict):  # already have keys, just recurse
       return {key: treeify(children) for key, children in data.items()}
    elif isinstance(data, list):  # make keys from indices
       return {idx: treeify(children) for idx, children in enumerate(data, start=1)}
    else:  # leave node, no recursion
       return data

def main():
    tmp = {"node" : "3c:71:bb:e4:8b:89",
                      "child" : 
                      [
                         {"node" : "3c:71:bb:e4:8b:a1",
                          "child": 
                          [
                              {
                                  "node": "3c:71:bb:e4:8b:b9",
                                  "child": {}  
                              }
                          ]
                          }
                      ]
                      }

    top = treeify(tmp)
    print(top)

    tree = Tree()
    create_tree(top, tree, None)
    print("TREE: ", tree)

    childB = tree.search("childB")
    print("FOUND:", childB)

    # children = childB.get_children()
    # pint(children)
    # de = tree.del_node("childE")
    # print(tree)

    print(tree.pack())
    # x = json.dumps(tree.__repr__())
    # print("JSON:" , x)

    def id_generator(dict_var):
        for k, v in dict_var.items():
            if k == "node":
                yield v
            elif isinstance(v, dict):
                for id_val in id_generator(v):
                    yield id_val
            elif isinstance(v, list):
                for item in v:
                    yield from id_generator(v)

    all_nodes = id_generator(top)
    for i in all_nodes:
        print(i)

if __name__ == "__main__":
    main()


