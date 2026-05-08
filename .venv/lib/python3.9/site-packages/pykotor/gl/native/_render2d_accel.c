/**
 * _render2d_accel.c - C acceleration for 2D walkmesh/map renderer hot paths.
 *
 * Provides:
 *   - batch_point_in_triangles: find which triangle (face) contains a 2D point
 *   - batch_distances_2d: compute squared distances from N positions to a query point
 *   - batch_face_at: combined faceAt for flat vertex/face arrays
 *   - batch_material_groups: group face indices by material for batch QPainter draws
 *
 * Build: compiled as a Python C extension via setuptools (OptionalBuildExt).
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <float.h>
#include <string.h>

/* --------------------------------------------------------------------------
 * batch_point_in_triangles(vertices_flat, face_indices_flat, qx, qy)
 *
 * Tests a 2D point (qx, qy) against N triangles defined by vertex positions
 * and face index triplets. Returns the index of the first triangle containing
 * the point, or -1 if none.
 *
 * vertices_flat: bytes of V×2 floats (x, y per vertex)
 * face_indices_flat: bytes of N×3 int32 (v1_idx, v2_idx, v3_idx per face)
 * qx, qy: query point coordinates
 *
 * Returns: int (face index, or -1)
 * -------------------------------------------------------------------------- */

static PyObject *
render2d_batch_point_in_triangles(PyObject *self, PyObject *args) {
    Py_buffer verts_buf, faces_buf;
    float qx, qy;

    if (!PyArg_ParseTuple(args, "y*y*ff", &verts_buf, &faces_buf, &qx, &qy)) {
        return NULL;
    }

    Py_ssize_t num_verts = verts_buf.len / (2 * (Py_ssize_t)sizeof(float));
    Py_ssize_t num_faces = faces_buf.len / (3 * (Py_ssize_t)sizeof(int));

    if (verts_buf.len != num_verts * 2 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&verts_buf);
        PyBuffer_Release(&faces_buf);
        PyErr_SetString(PyExc_ValueError, "vertices must be V×2 floats");
        return NULL;
    }

    if (faces_buf.len != num_faces * 3 * (Py_ssize_t)sizeof(int)) {
        PyBuffer_Release(&verts_buf);
        PyBuffer_Release(&faces_buf);
        PyErr_SetString(PyExc_ValueError, "face_indices must be N×3 int32");
        return NULL;
    }

    const float *verts = (const float *)verts_buf.buf;
    const int *faces = (const int *)faces_buf.buf;

    for (Py_ssize_t i = 0; i < num_faces; i++) {
        int i1 = faces[i * 3 + 0];
        int i2 = faces[i * 3 + 1];
        int i3 = faces[i * 3 + 2];

        /* Bounds check indices */
        if (i1 < 0 || i1 >= num_verts || i2 < 0 || i2 >= num_verts || i3 < 0 || i3 >= num_verts) {
            continue;
        }

        float v1x = verts[i1 * 2], v1y = verts[i1 * 2 + 1];
        float v2x = verts[i2 * 2], v2y = verts[i2 * 2 + 1];
        float v3x = verts[i3 * 2], v3y = verts[i3 * 2 + 1];

        /* Cross-product edge tests (same as BWM.faceAt) */
        float c1 = (v2x - v1x) * (qy - v1y) - (v2y - v1y) * (qx - v1x);
        float c2 = (v3x - v2x) * (qy - v2y) - (v3y - v2y) * (qx - v2x);
        float c3 = (v1x - v3x) * (qy - v3y) - (v1y - v3y) * (qx - v3x);

        if ((c1 < 0.0f && c2 < 0.0f && c3 < 0.0f) ||
            (c1 > 0.0f && c2 > 0.0f && c3 > 0.0f)) {
            PyBuffer_Release(&verts_buf);
            PyBuffer_Release(&faces_buf);
            return PyLong_FromSsize_t(i);
        }
    }

    PyBuffer_Release(&verts_buf);
    PyBuffer_Release(&faces_buf);
    return PyLong_FromLong(-1);
}


/* --------------------------------------------------------------------------
 * batch_distances_2d(positions_flat, qx, qy)
 *
 * Compute squared Euclidean distance from each position to a query point.
 * Returns an array of squared distances (caller can compare against
 * threshold² to avoid sqrt).
 *
 * positions_flat: bytes of N×2 floats (x, y per position)
 * qx, qy: query point coordinates
 *
 * Returns: bytes of N floats (squared distances)
 * -------------------------------------------------------------------------- */

static PyObject *
render2d_batch_distances_2d(PyObject *self, PyObject *args) {
    Py_buffer pos_buf;
    float qx, qy;

    if (!PyArg_ParseTuple(args, "y*ff", &pos_buf, &qx, &qy)) {
        return NULL;
    }

    Py_ssize_t num_positions = pos_buf.len / (2 * (Py_ssize_t)sizeof(float));
    if (pos_buf.len != num_positions * 2 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&pos_buf);
        PyErr_SetString(PyExc_ValueError, "positions must be N×2 floats");
        return NULL;
    }

    const float *positions = (const float *)pos_buf.buf;

    Py_ssize_t result_bytes = num_positions * (Py_ssize_t)sizeof(float);
    PyObject *result = PyBytes_FromStringAndSize(NULL, result_bytes);
    if (!result) {
        PyBuffer_Release(&pos_buf);
        return NULL;
    }

    float *dists = (float *)PyBytes_AS_STRING(result);

    for (Py_ssize_t i = 0; i < num_positions; i++) {
        float dx = positions[i * 2] - qx;
        float dy = positions[i * 2 + 1] - qy;
        dists[i] = dx * dx + dy * dy;
    }

    PyBuffer_Release(&pos_buf);
    return result;
}


/* --------------------------------------------------------------------------
 * batch_distances_2d_filtered(positions_flat, qx, qy, threshold_sq)
 *
 * Returns a list of integer indices where the squared distance is
 * <= threshold_sq.  More efficient than returning all distances when
 * only the "hit" set matters.
 *
 * positions_flat: bytes of N×2 floats (x, y per position)
 * qx, qy: query point coordinates
 * threshold_sq: float (threshold squared)
 *
 * Returns: list[int] of indices within threshold
 * -------------------------------------------------------------------------- */

static PyObject *
render2d_batch_distances_2d_filtered(PyObject *self, PyObject *args) {
    Py_buffer pos_buf;
    float qx, qy, threshold_sq;

    if (!PyArg_ParseTuple(args, "y*fff", &pos_buf, &qx, &qy, &threshold_sq)) {
        return NULL;
    }

    Py_ssize_t num_positions = pos_buf.len / (2 * (Py_ssize_t)sizeof(float));
    if (pos_buf.len != num_positions * 2 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&pos_buf);
        PyErr_SetString(PyExc_ValueError, "positions must be N×2 floats");
        return NULL;
    }

    const float *positions = (const float *)pos_buf.buf;

    PyObject *result_list = PyList_New(0);
    if (!result_list) {
        PyBuffer_Release(&pos_buf);
        return NULL;
    }

    for (Py_ssize_t i = 0; i < num_positions; i++) {
        float dx = positions[i * 2] - qx;
        float dy = positions[i * 2 + 1] - qy;
        float dist_sq = dx * dx + dy * dy;
        if (dist_sq <= threshold_sq) {
            PyObject *idx = PyLong_FromSsize_t(i);
            if (!idx) {
                Py_DECREF(result_list);
                PyBuffer_Release(&pos_buf);
                return NULL;
            }
            if (PyList_Append(result_list, idx) < 0) {
                Py_DECREF(idx);
                Py_DECREF(result_list);
                PyBuffer_Release(&pos_buf);
                return NULL;
            }
            Py_DECREF(idx);
        }
    }

    PyBuffer_Release(&pos_buf);
    return result_list;
}


/* --------------------------------------------------------------------------
 * batch_face_at_direct(vertices_flat_xy, num_faces, qx, qy)
 *
 * Simplified point-in-triangle for BWM.faceAt: vertices are already
 * inlined as 6 floats per face (v1x, v1y, v2x, v2y, v3x, v3y).
 *
 * This avoids the indirection of face_indices + vertex arrays, saving
 * memory lookups per face test.
 *
 * vertices_flat_xy: bytes of N×6 floats (v1x, v1y, v2x, v2y, v3x, v3y per face)
 * qx, qy: query point
 *
 * Returns: int (face index, or -1)
 * -------------------------------------------------------------------------- */

static PyObject *
render2d_batch_face_at_direct(PyObject *self, PyObject *args) {
    Py_buffer verts_buf;
    float qx, qy;

    if (!PyArg_ParseTuple(args, "y*ff", &verts_buf, &qx, &qy)) {
        return NULL;
    }

    Py_ssize_t num_faces = verts_buf.len / (6 * (Py_ssize_t)sizeof(float));
    if (verts_buf.len != num_faces * 6 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&verts_buf);
        PyErr_SetString(PyExc_ValueError, "vertices must be N×6 floats (v1x, v1y, v2x, v2y, v3x, v3y per face)");
        return NULL;
    }

    const float *verts = (const float *)verts_buf.buf;

    for (Py_ssize_t i = 0; i < num_faces; i++) {
        const float *f = &verts[i * 6];
        float v1x = f[0], v1y = f[1];
        float v2x = f[2], v2y = f[3];
        float v3x = f[4], v3y = f[5];

        float c1 = (v2x - v1x) * (qy - v1y) - (v2y - v1y) * (qx - v1x);
        float c2 = (v3x - v2x) * (qy - v2y) - (v3y - v2y) * (qx - v2x);
        float c3 = (v1x - v3x) * (qy - v3y) - (v1y - v3y) * (qx - v3x);

        if ((c1 < 0.0f && c2 < 0.0f && c3 < 0.0f) ||
            (c1 > 0.0f && c2 > 0.0f && c3 > 0.0f)) {
            PyBuffer_Release(&verts_buf);
            return PyLong_FromSsize_t(i);
        }
    }

    PyBuffer_Release(&verts_buf);
    return PyLong_FromLong(-1);
}


/* --------------------------------------------------------------------------
 * batch_group_faces_by_material(materials_flat, num_materials)
 *
 * Group face indices by their material value for batch QPainter draws.
 * Returns a dict { int(material) -> list[int](face_indices) }.
 *
 * materials_flat: bytes of N int32 (material per face)
 *
 * Returns: dict[int, list[int]]
 * -------------------------------------------------------------------------- */

static PyObject *
render2d_batch_group_faces_by_material(PyObject *self, PyObject *args) {
    Py_buffer mat_buf;

    if (!PyArg_ParseTuple(args, "y*", &mat_buf)) {
        return NULL;
    }

    Py_ssize_t num_faces = mat_buf.len / (Py_ssize_t)sizeof(int);
    if (mat_buf.len != num_faces * (Py_ssize_t)sizeof(int)) {
        PyBuffer_Release(&mat_buf);
        PyErr_SetString(PyExc_ValueError, "materials must be N int32");
        return NULL;
    }

    const int *materials = (const int *)mat_buf.buf;

    PyObject *result_dict = PyDict_New();
    if (!result_dict) {
        PyBuffer_Release(&mat_buf);
        return NULL;
    }

    for (Py_ssize_t i = 0; i < num_faces; i++) {
        int mat = materials[i];
        PyObject *mat_key = PyLong_FromLong(mat);
        if (!mat_key) {
            Py_DECREF(result_dict);
            PyBuffer_Release(&mat_buf);
            return NULL;
        }

        PyObject *face_list = PyDict_GetItemWithError(result_dict, mat_key);
        if (face_list == NULL) {
            if (PyErr_Occurred()) {
                Py_DECREF(mat_key);
                Py_DECREF(result_dict);
                PyBuffer_Release(&mat_buf);
                return NULL;
            }
            face_list = PyList_New(0);
            if (!face_list) {
                Py_DECREF(mat_key);
                Py_DECREF(result_dict);
                PyBuffer_Release(&mat_buf);
                return NULL;
            }
            if (PyDict_SetItem(result_dict, mat_key, face_list) < 0) {
                Py_DECREF(face_list);
                Py_DECREF(mat_key);
                Py_DECREF(result_dict);
                PyBuffer_Release(&mat_buf);
                return NULL;
            }
            Py_DECREF(face_list);  /* dict holds the reference now */
            face_list = PyDict_GetItemWithError(result_dict, mat_key);
        }
        Py_DECREF(mat_key);

        PyObject *idx = PyLong_FromSsize_t(i);
        if (!idx) {
            Py_DECREF(result_dict);
            PyBuffer_Release(&mat_buf);
            return NULL;
        }
        if (PyList_Append(face_list, idx) < 0) {
            Py_DECREF(idx);
            Py_DECREF(result_dict);
            PyBuffer_Release(&mat_buf);
            return NULL;
        }
        Py_DECREF(idx);
    }

    PyBuffer_Release(&mat_buf);
    return result_dict;
}


/* --------------------------------------------------------------------------
 * batch_compute_aabb_2d(vertices_flat)
 *
 * Compute 2D AABB (min_x, min_y, max_x, max_y) from flat vertices.
 *
 * vertices_flat: bytes of N×2 floats (x, y per vertex)
 *
 * Returns: tuple(min_x, min_y, max_x, max_y)
 * -------------------------------------------------------------------------- */

static PyObject *
render2d_batch_compute_aabb_2d(PyObject *self, PyObject *args) {
    Py_buffer verts_buf;

    if (!PyArg_ParseTuple(args, "y*", &verts_buf)) {
        return NULL;
    }

    Py_ssize_t num_verts = verts_buf.len / (2 * (Py_ssize_t)sizeof(float));
    if (num_verts == 0) {
        PyBuffer_Release(&verts_buf);
        return Py_BuildValue("(ffff)", 0.0f, 0.0f, 0.0f, 0.0f);
    }

    const float *verts = (const float *)verts_buf.buf;
    float minx = verts[0], miny = verts[1];
    float maxx = verts[0], maxy = verts[1];

    for (Py_ssize_t i = 1; i < num_verts; i++) {
        float x = verts[i * 2], y = verts[i * 2 + 1];
        if (x < minx) minx = x;
        if (x > maxx) maxx = x;
        if (y < miny) miny = y;
        if (y > maxy) maxy = y;
    }

    PyBuffer_Release(&verts_buf);
    return Py_BuildValue("(ffff)", minx, miny, maxx, maxy);
}


/* --------------------------------------------------------------------------
 * Module definition
 * -------------------------------------------------------------------------- */

static PyMethodDef Render2dAccelMethods[] = {
    {"batch_point_in_triangles", render2d_batch_point_in_triangles, METH_VARARGS,
     "Find which triangle contains a 2D point.\n\n"
     "Args:\n"
     "    vertices_flat: bytes of V×2 floats (x, y per vertex)\n"
     "    face_indices_flat: bytes of N×3 int32 (v1, v2, v3 per face)\n"
     "    qx, qy: query point\n\n"
     "Returns:\n"
     "    int: face index containing point, or -1"},

    {"batch_distances_2d", render2d_batch_distances_2d, METH_VARARGS,
     "Compute squared 2D distances from N positions to a query point.\n\n"
     "Args:\n"
     "    positions_flat: bytes of N×2 floats\n"
     "    qx, qy: query point\n\n"
     "Returns:\n"
     "    bytes of N floats (squared distances)"},

    {"batch_distances_2d_filtered", render2d_batch_distances_2d_filtered, METH_VARARGS,
     "Return indices of positions within threshold distance of query point.\n\n"
     "Args:\n"
     "    positions_flat: bytes of N×2 floats\n"
     "    qx, qy: query point\n"
     "    threshold_sq: float (threshold squared)\n\n"
     "Returns:\n"
     "    list[int]: indices within threshold"},

    {"batch_face_at_direct", render2d_batch_face_at_direct, METH_VARARGS,
     "Point-in-triangle for inlined face vertices (6 floats per face).\n\n"
     "This is the fastest path for BWM.faceAt: no index indirection.\n\n"
     "Args:\n"
     "    vertices_flat_xy: bytes of N×6 floats (v1x,v1y,v2x,v2y,v3x,v3y)\n"
     "    qx, qy: query point\n\n"
     "Returns:\n"
     "    int: face index, or -1"},

    {"batch_group_faces_by_material", render2d_batch_group_faces_by_material, METH_VARARGS,
     "Group face indices by material value for batch draws.\n\n"
     "Args:\n"
     "    materials_flat: bytes of N int32\n\n"
     "Returns:\n"
     "    dict[int, list[int]]"},

    {"batch_compute_aabb_2d", render2d_batch_compute_aabb_2d, METH_VARARGS,
     "Compute 2D AABB from flat vertex array.\n\n"
     "Args:\n"
     "    vertices_flat: bytes of V×2 floats\n\n"
     "Returns:\n"
     "    tuple(min_x, min_y, max_x, max_y)"},

    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef render2d_accel_module = {
    PyModuleDef_HEAD_INIT,
    "_render2d_accel",
    "C acceleration for PyKotor 2D walkmesh/map renderer.\n\n"
    "Batch point-in-triangle, distance, and material grouping operations\n"
    "that replace per-face and per-instance Python loops in paintEvent.",
    -1,
    Render2dAccelMethods
};

PyMODINIT_FUNC
PyInit__render2d_accel(void) {
    return PyModule_Create(&render2d_accel_module);
}
