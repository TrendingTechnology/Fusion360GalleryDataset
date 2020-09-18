"""

Reconstruct from a json design

"""

import adsk.core
import adsk.fusion
import os
import sys
import importlib
import math

from .command_base import CommandBase

# Add the common folder to sys.path
COMMON_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "common"))
if COMMON_DIR not in sys.path:
    sys.path.append(COMMON_DIR)

import deserialize
import serialize
import match
from sketch_extrude_importer import SketchExtrudeImporter


class CommandReconstruct(CommandBase):

    def reconstruct(self, data):
        """Reconstruct a design from the provided json data"""
        importer = SketchExtrudeImporter(data)
        importer.reconstruct()
        return self.runner.return_success()

    def reconstruct_sketch(self, data):
        if (data is None or "json_data" not in data or
           "sketch_name" not in data):
            return self.runner.return_failure("reconstruct_sketch data not specified")
        json_data = data["json_data"]
        sketch_name = data["sketch_name"]
        if json_data is None:
            return self.runner.return_failure("reconstruct json not found")
        if sketch_name is None:
            return self.runner.return_failure("reconstruct sketch not found")
        entities = json_data["entities"]
        if entities is None:
            return self.runner.return_failure("reconstruct entities not found")
        # retrieve sketch id from sketch name
        sketch_uuid = None
        for entity in entities:
            if entities[entity]["name"] == sketch_name:
                sketch_uuid = entity
        if sketch_uuid is None:
            return self.runner.return_failure("reconstruct sketch id doesn't exist")
        # Optional sketch plane
        sketch_plane = None
        if "sketch_plane" in data:
            sketch_plane = match.sketch_plane(data["sketch_plane"])
        # Optional transform
        scale = None
        translate = None
        rotate = None
        if "scale" in data:
            scale = deserialize.vector3d(data["scale"])
        if "translate" in data:
            translate = deserialize.vector3d(data["translate"])
        if "rotate" in data:
            rotate = deserialize.vector3d(data["rotate"])
        transform = None
        if scale is not None or translate is not None or rotate is not None or sketch_plane is not None:
            # Get the transform or an identity matrix
            transform = self.__get_transform_matrix(scale, translate, rotate)
        # Create the sketch
        importer = SketchExtrudeImporter(json_data)
        sketch = importer.reconstruct_sketch(sketch_uuid, sketch_plane=sketch_plane, transform=transform)
        # Serialize the data and return
        profile_data = serialize.sketch_profiles(sketch.profiles)
        return self.runner.return_success({
            "sketch_id": sketch_uuid,
            "sketch_name": sketch.name,
            "profiles": profile_data
        })

    def __get_transform_matrix(self, scale=None, translation=None, rotate=None):
        """Get a transformation matrix that scales, translates, and rotates"""
        transform = adsk.core.Matrix3D.create()
        if scale is not None:
            # We don't have a Matrix3D.scale() function
            # so we set this manually
            scale_matrix = [
                [scale.x, 0, 0, 0],
                [0, scale.y, 0, 0],
                [0, 0, scale.z, 0],
                [0, 0, 0, 1]
            ]
        else:
            # create identity matrix
            # do we have Matrix3D.identity()?
            scale_matrix = [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ]
        if translation is not None:
            # We do have a shortcut to set the translation
            # transform.translation = translation
            # we don't use the shortcut here as we need to cumulate all the transforms later
            translate_matrix = [
                [1, 0, 0, translation.x],
                [0, 1, 0, translation.y],
                [0, 0, 1, translation.z],
                [0, 0, 0, 1]
            ]
        else:
            translate_matrix = [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ]
        if rotate is not None:
            thetaX = math.radians(rotate.x)
            rotateX_matrix = [
                [1, 0, 0, 0],
                [0, math.cos(thetaX), math.sin(thetaX), 0],
                [0, -math.sin(thetaX), math.cos(thetaX), 0],
                [0, 0, 0, 1]
            ]
            thetaY = math.radians(rotate.y)
            rotateY_matrix = [
                [math.cos(thetaY), 0, -math.sin(thetaY), 0],
                [0, 1, 0, 0],
                [math.sin(thetaY), 0, math.cos(thetaY), 0],
                [0, 0, 0, 1]
            ]
            thetaZ = math.radians(rotate.z)
            rotateZ_matrix = [
                [math.cos(thetaZ), -math.sin(thetaZ), 0, 0],
                [math.sin(thetaZ), math.cos(thetaZ), 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ]
            # multiply three rotate matrices 
            rotate_matrix = self.__matrix_multiplication(rotateX_matrix, rotateY_matrix)
            rotate_matrix = self.__matrix_multiplication(rotate_matrix, rotateZ_matrix)
        else:
            rotate_matrix = [
                [1, 0, 0, 0],
                [0, 1, 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1]
            ]
        # multiply translate, rotate, scale matrix
        # performs scale first, rotate second, translate last
        transform_matrix = self.__matrix_multiplication(translate_matrix, rotate_matrix)
        transform_matrix = self.__matrix_multiplication(transform_matrix, scale_matrix)
        # shape the transform matrix to 1D array 
        transform_matrix = self.__reshape_1D(transform_matrix) 
        transform.setWithArray(transform_matrix)
        return transform

    def __matrix_multiplication(self, X, Y):
        return [[sum(a*b for a,b in zip(X_row,Y_col)) for Y_col in zip(*Y)] for X_row in X]

    def __reshape_1D(self, matrix):
        '''reshape a matrix into an array'''
        array = []
        for row in matrix:
            for element in row:
                array.append(element)
        return array
