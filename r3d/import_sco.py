import struct
import sys
import os
import timeit
import threading
import pdb

import bpy
import mathutils
import os.path
from bpy.props import *
from bpy_extras.image_utils import load_image
from ast import literal_eval as make_tuple

from math import sqrt
from math import atan2

import re

from configparser import RawConfigParser, NoOptionError

import bmesh

class MaterialParser(RawConfigParser):
    def get(self, section, option):
        try:
            return RawConfigParser.get(self, section, option)
        except NoOptionError:
            return None

def countGlobalPosition(coords1, coords2):
    result = [0.0, 0.0, 0.0]
    if (coords1[0] <= 0):
        result[0] = coords1[0] - coords2[0]
    else:
        result[0] = coords1[0] + coords2[0]

    if (coords1[1] <= 0):
        result[1] = coords1[1] - coords2[1]
    else:
        result[1] = coords1[1] + coords2[1]

    if (coords1[2] <= 0):
        result[2] = coords1[2] - coords2[2]
    else:
        result[2] = coords1[2] + coords2[2]

    return result


def LoadFromSCO_Object(file, context, op, filepath):
    sco_lines = file.readlines()

    name = ''
    central_point = [0.0, 0.0, 0.0]
    num_verts = 0
    num_faces = 0
    verts_data = []
    faces_data = []
    faces_uv = []
    mats_data = []

    faces_all_data = []

    used_materials_list = []

    iter = 0
    while(True):
        test_str_strip = sco_lines[iter].strip()
        iter += 1

        if (test_str_strip[:4] == "Name"):
            name = test_str_strip.split(sep='=')[1].strip()
        elif (test_str_strip[:12] == "CentralPoint"):
            temp_vector = test_str_strip.split(sep='=')[1].strip().split(sep=' ')
            central_point[0] = float(temp_vector[0])
            central_point[1] = float(temp_vector[1])
            central_point[2] = float(temp_vector[2])
        elif (test_str_strip[:5] == "Verts"):
            num_verts = int(test_str_strip.split(sep='=')[1].strip())
            break

    for i in range(num_verts):
        test_str_strip = sco_lines[i + iter].strip()
        temp_vector = test_str_strip.strip().split(sep=' ')

        verts_data.append((float(temp_vector[0]), float(
            temp_vector[2]), float(temp_vector[1])))

    iter += num_verts

    num_faces = int(sco_lines[iter].strip().split(sep='=')[1].strip())
    iter += 1

    for i in range(num_faces):
        test_str_strip = sco_lines[i + iter].strip()

        temp_data = test_str_strip.strip().split()
        # print(temp_data)

        temp_face = []
        temp_uv = []
        uv_offset = 0
        for k in range(int(temp_data[0])):
            temp_face.append(int(temp_data[k + 1]))
            temp_uv.append([float(temp_data[k + uv_offset + 5]),
                           1 - float(temp_data[k + uv_offset + 6])])
            uv_offset += 1

        faces_data.append((temp_face))

        mats_data.append(temp_data[4])

        if not (temp_data[4] in bpy.data.materials):
            bpy.data.materials.new(temp_data[4])

        if not (temp_data[4] in used_materials_list):
            used_materials_list.append(temp_data[4])

        faces_uv.append(temp_uv)

        faces_all_data.append(temp_data)

    scoMesh = (bpy.data.meshes.new(name))
    scoObj = bpy.data.objects.new(name, scoMesh)

    # print(used_materials_list)

    for i in range(len(used_materials_list)):

        print("Loading Material %s..." % used_materials_list[i])

        material = bpy.data.materials[used_materials_list[i]]
        material.use_nodes = True

        material_ini = MaterialParser(allow_no_value=True)

        base_dir = '\\'.join(filepath.split('\\')[:-1])

        mat_path = base_dir + '\\Materials\\' + used_materials_list[i] + '.mat'

        # material_ini.read(str(os.path.dirname(file)) + '/Materials/' + str(i) + '.mat')
        material_ini.read(mat_path)

        if material_ini:

            node_tree = material.node_tree
            bsdf = material.node_tree.nodes["Principled BSDF"]

            textureName = material_ini.get('MaterialBegin', 'Texture')
            normalName = material_ini.get('MaterialBegin', 'NormalMap')
            specularName = material_ini.get('MaterialBegin', 'SpecularMap')

            if textureName:
                textureNode = node_tree.nodes.new('ShaderNodeTexImage')
                textureNode.image = bpy.data.images.load(base_dir + '\\Textures\\' + textureName)
                material.node_tree.links.new(bsdf.inputs['Base Color'], textureNode.outputs['Color'])

            if specularName:
                specularNode = node_tree.nodes.new('ShaderNodeTexImage')
                specularNode.image = bpy.data.images.load(base_dir + '\\Textures\\' + specularName)
                material.node_tree.links.new(bsdf.inputs['Specular'], specularNode.outputs['Color'])

            if normalName:
                normalTextureNode = node_tree.nodes.new('ShaderNodeTexImage')
                normalMapNode = node_tree.nodes.new('ShaderNodeNormalMap')

                normalTextureNode.image = bpy.data.images.load(base_dir + '\\Textures\\' + normalName)
                material.node_tree.links.new(normalMapNode.inputs['Color'], normalTextureNode.outputs['Color'])
                material.node_tree.links.new(bsdf.inputs['Normal'], normalMapNode.outputs['Normal'])

        scoObj.data.materials.append(material)

    # print(scoObj.data.materials)
        
    Ev = threading.Event()
    Tr = threading.Thread(target=scoMesh.from_pydata, args = (verts_data, [], faces_data))
    Tr.start()
    Ev.set()
    Tr.join()
                
    context.scene.collection.objects.link(scoObj)

    bm = bmesh.new()
    bm.from_mesh(scoMesh)
    uv_layer = bm.loops.layers.uv.verify()
                
    # https://blender.stackexchange.com/questions/185496/how-to-unwrap-a-mesh-from-view-in-python-blender-2-8

    i = 0
    
    for face in bm.faces:
        k = 0
        
        face.material_index = used_materials_list.index(mats_data[i])
        
        for loop in face.loops:
            loop_uv = loop[uv_layer]
            loop_uv.uv = faces_uv[i][k]
            
            # i - face index
            # k - vert num (not index)
            # print('i={}, k={}'.format(i, k))
            k += 1
        i += 1
        
        face.smooth = True

    scoObj.location.x = central_point[0]
    scoObj.location.y = central_point[2]
    scoObj.location.z = central_point[1]
    
    for v in bm.verts:
        v.co.x -= scoObj.location.x
        v.co.y -= scoObj.location.y
        v.co.z -= scoObj.location.z
    
    """
    for v in bm.verts:
        if (v.co.x <= 0):
            v.co.x += scoObj.location.x
        else:
            v.co.x -= scoObj.location.x
            
        if (v.co.y <= 0):
            v.co.y += scoObj.location.y
        else:
            v.co.y -= scoObj.location.y
            
        if (v.co.z <= 0):
            v.co.z += scoObj.location.z
        else:
            v.co.z -= scoObj.location.z
    """
    
    bm.to_mesh(scoMesh)
    scoMesh.update()

def read(file, context, op, filepath):
    LoadFromSCO_Object(file, context, op, filepath)
