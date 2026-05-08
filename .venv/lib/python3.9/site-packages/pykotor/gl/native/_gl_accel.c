/**
 * _gl_accel.c - C acceleration for PyKotor GL rendering pipeline.
 *
 * Provides batch frustum culling, transform bounds, and other
 * performance-critical operations that are called per-frame in the
 * module designer's render loop.
 *
 * Build: compiled as a Python C extension via setuptools.
 */

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <math.h>
#include <string.h>
#include <float.h>

/* --------------------------------------------------------------------------
 * Frustum plane: (nx, ny, nz, d) packed as 4 floats.
 * 6 planes: LEFT, RIGHT, BOTTOM, TOP, NEAR, FAR.
 * -------------------------------------------------------------------------- */

typedef struct {
    float nx, ny, nz, d;
} Plane;

typedef struct {
    Plane planes[6];
} Frustum;

/* --------------------------------------------------------------------------
 * Bounding sphere for each object: (cx, cy, cz, radius).
 * -------------------------------------------------------------------------- */

typedef struct {
    float cx, cy, cz, radius;
} Sphere;

/* --------------------------------------------------------------------------
 * sphere_in_frustum: test a single sphere against all 6 planes.
 * Returns 1 if visible, 0 if culled.
 * -------------------------------------------------------------------------- */

static inline int sphere_in_frustum(const Frustum *f, float cx, float cy, float cz, float radius) {
    for (int i = 0; i < 6; i++) {
        float dist = f->planes[i].nx * cx
                   + f->planes[i].ny * cy
                   + f->planes[i].nz * cz
                   + f->planes[i].d;
        if (dist < -radius) {
            return 0;
        }
    }
    return 1;
}

/* --------------------------------------------------------------------------
 * batch_frustum_cull(planes_flat, spheres_flat)
 *
 * planes_flat: list/tuple of 24 floats (6 planes × 4 components)
 * spheres_flat: list/tuple of N×4 floats (cx, cy, cz, radius per object)
 *
 * Returns: bytearray of N bytes, 1=visible, 0=culled.
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_batch_frustum_cull(PyObject *self, PyObject *args) {
    Py_buffer planes_buf, spheres_buf;

    if (!PyArg_ParseTuple(args, "y*y*", &planes_buf, &spheres_buf)) {
        return NULL;
    }

    if (planes_buf.len != 24 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&planes_buf);
        PyBuffer_Release(&spheres_buf);
        PyErr_SetString(PyExc_ValueError, "planes must be 24 floats (6 planes × 4 components)");
        return NULL;
    }

    Py_ssize_t num_objects = spheres_buf.len / (4 * (Py_ssize_t)sizeof(float));
    if (spheres_buf.len != num_objects * 4 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&planes_buf);
        PyBuffer_Release(&spheres_buf);
        PyErr_SetString(PyExc_ValueError, "spheres must be N×4 floats");
        return NULL;
    }

    const float *planes_f = (const float *)planes_buf.buf;
    const float *spheres_f = (const float *)spheres_buf.buf;

    Frustum frustum;
    for (int i = 0; i < 6; i++) {
        frustum.planes[i].nx = planes_f[i * 4 + 0];
        frustum.planes[i].ny = planes_f[i * 4 + 1];
        frustum.planes[i].nz = planes_f[i * 4 + 2];
        frustum.planes[i].d  = planes_f[i * 4 + 3];
    }

    PyObject *result = PyByteArray_FromStringAndSize(NULL, num_objects);
    if (!result) {
        PyBuffer_Release(&planes_buf);
        PyBuffer_Release(&spheres_buf);
        return NULL;
    }

    char *visibility = PyByteArray_AS_STRING(result);

    for (Py_ssize_t i = 0; i < num_objects; i++) {
        float cx = spheres_f[i * 4 + 0];
        float cy = spheres_f[i * 4 + 1];
        float cz = spheres_f[i * 4 + 2];
        float r  = spheres_f[i * 4 + 3];
        visibility[i] = (char)sphere_in_frustum(&frustum, cx, cy, cz, r);
    }

    PyBuffer_Release(&planes_buf);
    PyBuffer_Release(&spheres_buf);
    return result;
}

/* --------------------------------------------------------------------------
 * extract_frustum_planes(vp_matrix_flat)
 *
 * vp_matrix_flat: bytes/bytearray of 16 floats (4×4 column-major matrix)
 *
 * Returns: bytes of 24 floats (6 normalized planes).
 *
 * Implements the Gribb/Hartmann frustum plane extraction method.
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_extract_frustum_planes(PyObject *self, PyObject *args) {
    Py_buffer vp_buf;

    if (!PyArg_ParseTuple(args, "y*", &vp_buf)) {
        return NULL;
    }

    if (vp_buf.len != 16 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&vp_buf);
        PyErr_SetString(PyExc_ValueError, "vp_matrix must be 16 floats (4×4 column-major)");
        return NULL;
    }

    /* Column-major: vp[col][row] => flat index = col*4 + row */
    const float *m = (const float *)vp_buf.buf;

    /* Helper: m[col][row] = m[col*4 + row] */
    #define M(col, row) m[(col)*4 + (row)]

    float planes[24];

    /* Left: row3 + row0 */
    planes[0]  = M(0,3) + M(0,0);
    planes[1]  = M(1,3) + M(1,0);
    planes[2]  = M(2,3) + M(2,0);
    planes[3]  = M(3,3) + M(3,0);

    /* Right: row3 - row0 */
    planes[4]  = M(0,3) - M(0,0);
    planes[5]  = M(1,3) - M(1,0);
    planes[6]  = M(2,3) - M(2,0);
    planes[7]  = M(3,3) - M(3,0);

    /* Bottom: row3 + row1 */
    planes[8]  = M(0,3) + M(0,1);
    planes[9]  = M(1,3) + M(1,1);
    planes[10] = M(2,3) + M(2,1);
    planes[11] = M(3,3) + M(3,1);

    /* Top: row3 - row1 */
    planes[12] = M(0,3) - M(0,1);
    planes[13] = M(1,3) - M(1,1);
    planes[14] = M(2,3) - M(2,1);
    planes[15] = M(3,3) - M(3,1);

    /* Near: row3 + row2 */
    planes[16] = M(0,3) + M(0,2);
    planes[17] = M(1,3) + M(1,2);
    planes[18] = M(2,3) + M(2,2);
    planes[19] = M(3,3) + M(3,2);

    /* Far: row3 - row2 */
    planes[20] = M(0,3) - M(0,2);
    planes[21] = M(1,3) - M(1,2);
    planes[22] = M(2,3) - M(2,2);
    planes[23] = M(3,3) - M(3,2);

    #undef M

    /* Normalize each plane */
    for (int i = 0; i < 6; i++) {
        float *p = &planes[i * 4];
        float len = sqrtf(p[0]*p[0] + p[1]*p[1] + p[2]*p[2]);
        if (len > 1e-10f) {
            float inv = 1.0f / len;
            p[0] *= inv;
            p[1] *= inv;
            p[2] *= inv;
            p[3] *= inv;
        } else {
            p[0] = 0.0f;
            p[1] = 0.0f;
            p[2] = 1.0f;
            p[3] = 1e10f;
        }
    }

    PyBuffer_Release(&vp_buf);
    return PyBytes_FromStringAndSize((const char *)planes, sizeof(planes));
}

/* --------------------------------------------------------------------------
 * transform_bounds(vertex_data, vertex_count, stride, pos_offset, matrix)
 *
 * Compute AABB of transformed vertices. Replaces the CFFI version.
 *
 * vertex_data: buffer (bytes-like) of vertex data
 * vertex_count: int
 * stride: int (bytes between vertices)
 * pos_offset: int (byte offset to position within each vertex)
 * matrix: bytes of 16 floats (4×4 column-major)
 *
 * Returns: tuple((min_x, min_y, min_z), (max_x, max_y, max_z))
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_transform_bounds(PyObject *self, PyObject *args) {
    Py_buffer vert_buf, mat_buf;
    int vertex_count, stride, pos_offset;

    if (!PyArg_ParseTuple(args, "y*iiiy*", &vert_buf, &vertex_count, &stride, &pos_offset, &mat_buf)) {
        return NULL;
    }

    if (mat_buf.len != 16 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&vert_buf);
        PyBuffer_Release(&mat_buf);
        PyErr_SetString(PyExc_ValueError, "matrix must be 16 floats");
        return NULL;
    }

    if (vertex_count <= 0 || stride <= 0) {
        PyBuffer_Release(&vert_buf);
        PyBuffer_Release(&mat_buf);
        return Py_BuildValue("((fff)(fff))", 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f);
    }

    const char *vdata = (const char *)vert_buf.buf;
    const float *matrix = (const float *)mat_buf.buf;

    /* Column-major matrix layout */
    const float m00 = matrix[0],  m01 = matrix[4], m02 = matrix[8],  m03 = matrix[12];
    const float m10 = matrix[1],  m11 = matrix[5], m12 = matrix[9],  m13 = matrix[13];
    const float m20 = matrix[2],  m21 = matrix[6], m22 = matrix[10], m23 = matrix[14];

    float minx, miny, minz, maxx, maxy, maxz;
    minx = miny = minz = FLT_MAX;
    maxx = maxy = maxz = -FLT_MAX;

    for (int i = 0; i < vertex_count; i++) {
        Py_ssize_t offset = (Py_ssize_t)i * stride + pos_offset;
        if (offset + 3 * (Py_ssize_t)sizeof(float) > vert_buf.len) break;

        const float *pos = (const float *)(vdata + offset);
        float x = pos[0], y = pos[1], z = pos[2];

        float tx = m00 * x + m01 * y + m02 * z + m03;
        float ty = m10 * x + m11 * y + m12 * z + m13;
        float tz = m20 * x + m21 * y + m22 * z + m23;

        if (tx < minx) minx = tx;
        if (tx > maxx) maxx = tx;
        if (ty < miny) miny = ty;
        if (ty > maxy) maxy = ty;
        if (tz < minz) minz = tz;
        if (tz > maxz) maxz = tz;
    }

    if (minx > maxx) {
        minx = miny = minz = maxx = maxy = maxz = 0.0f;
    }

    PyBuffer_Release(&vert_buf);
    PyBuffer_Release(&mat_buf);
    return Py_BuildValue("((fff)(fff))", minx, miny, minz, maxx, maxy, maxz);
}

/* --------------------------------------------------------------------------
 * batch_sphere_distances(planes_flat, spheres_flat)
 *
 * For LOD calculations: returns minimum signed distance from each sphere
 * to any frustum plane (for LOD selection).
 *
 * planes_flat: bytes of 24 floats
 * spheres_flat: bytes of N×4 floats
 *
 * Returns: bytes of N floats (min signed distance per object).
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_batch_sphere_distances(PyObject *self, PyObject *args) {
    Py_buffer planes_buf, spheres_buf;

    if (!PyArg_ParseTuple(args, "y*y*", &planes_buf, &spheres_buf)) {
        return NULL;
    }

    if (planes_buf.len != 24 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&planes_buf);
        PyBuffer_Release(&spheres_buf);
        PyErr_SetString(PyExc_ValueError, "planes must be 24 floats");
        return NULL;
    }

    Py_ssize_t num_objects = spheres_buf.len / (4 * (Py_ssize_t)sizeof(float));
    const float *planes_f = (const float *)planes_buf.buf;
    const float *spheres_f = (const float *)spheres_buf.buf;

    Frustum frustum;
    for (int i = 0; i < 6; i++) {
        frustum.planes[i].nx = planes_f[i * 4 + 0];
        frustum.planes[i].ny = planes_f[i * 4 + 1];
        frustum.planes[i].nz = planes_f[i * 4 + 2];
        frustum.planes[i].d  = planes_f[i * 4 + 3];
    }

    Py_ssize_t result_size = num_objects * (Py_ssize_t)sizeof(float);
    PyObject *result = PyBytes_FromStringAndSize(NULL, result_size);
    if (!result) {
        PyBuffer_Release(&planes_buf);
        PyBuffer_Release(&spheres_buf);
        return NULL;
    }

    float *distances = (float *)PyBytes_AS_STRING(result);

    for (Py_ssize_t i = 0; i < num_objects; i++) {
        float cx = spheres_f[i * 4 + 0];
        float cy = spheres_f[i * 4 + 1];
        float cz = spheres_f[i * 4 + 2];
        float r  = spheres_f[i * 4 + 3];

        float min_dist = FLT_MAX;
        for (int j = 0; j < 6; j++) {
            float dist = frustum.planes[j].nx * cx
                       + frustum.planes[j].ny * cy
                       + frustum.planes[j].nz * cz
                       + frustum.planes[j].d;
            float adj = dist + r;
            if (adj < min_dist) min_dist = adj;
        }
        distances[i] = min_dist;
    }

    PyBuffer_Release(&planes_buf);
    PyBuffer_Release(&spheres_buf);
    return result;
}

/* --------------------------------------------------------------------------
 * mat4_multiply_batch(transforms, parent_matrix)
 *
 * Multiply an array of 4×4 column-major matrices by a parent matrix.
 * Used for node tree traversal in the draw loop.
 *
 * transforms: bytes of N×16 floats (N 4×4 matrices)
 * parent_matrix: bytes of 16 floats
 *
 * Returns: bytes of N×16 floats (result matrices)
 * -------------------------------------------------------------------------- */

static inline void mat4_mul(const float *a, const float *b, float *out) {
    for (int col = 0; col < 4; col++) {
        for (int row = 0; row < 4; row++) {
            float sum = 0.0f;
            for (int k = 0; k < 4; k++) {
                sum += a[k * 4 + row] * b[col * 4 + k];
            }
            out[col * 4 + row] = sum;
        }
    }
}

static PyObject *
gl_accel_mat4_multiply_batch(PyObject *self, PyObject *args) {
    Py_buffer transforms_buf, parent_buf;

    if (!PyArg_ParseTuple(args, "y*y*", &transforms_buf, &parent_buf)) {
        return NULL;
    }

    if (parent_buf.len != 16 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&transforms_buf);
        PyBuffer_Release(&parent_buf);
        PyErr_SetString(PyExc_ValueError, "parent_matrix must be 16 floats");
        return NULL;
    }

    Py_ssize_t num_matrices = transforms_buf.len / (16 * (Py_ssize_t)sizeof(float));
    if (transforms_buf.len != num_matrices * 16 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&transforms_buf);
        PyBuffer_Release(&parent_buf);
        PyErr_SetString(PyExc_ValueError, "transforms must be N×16 floats");
        return NULL;
    }

    const float *transforms = (const float *)transforms_buf.buf;
    const float *parent = (const float *)parent_buf.buf;

    Py_ssize_t result_size = num_matrices * 16 * (Py_ssize_t)sizeof(float);
    PyObject *result = PyBytes_FromStringAndSize(NULL, result_size);
    if (!result) {
        PyBuffer_Release(&transforms_buf);
        PyBuffer_Release(&parent_buf);
        return NULL;
    }

    float *out = (float *)PyBytes_AS_STRING(result);

    for (Py_ssize_t i = 0; i < num_matrices; i++) {
        mat4_mul(parent, &transforms[i * 16], &out[i * 16]);
    }

    PyBuffer_Release(&transforms_buf);
    PyBuffer_Release(&parent_buf);
    return result;
}

/* --------------------------------------------------------------------------
 * aabb_in_frustum_batch(planes_flat, aabb_flat)
 *
 * planes_flat: bytes of 24 floats (6 planes)
 * aabb_flat: bytes of N×6 floats (min_x, min_y, min_z, max_x, max_y, max_z)
 *
 * Returns: bytearray of N bytes, 1=visible, 0=culled.
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_aabb_in_frustum_batch(PyObject *self, PyObject *args) {
    Py_buffer planes_buf, aabb_buf;

    if (!PyArg_ParseTuple(args, "y*y*", &planes_buf, &aabb_buf)) {
        return NULL;
    }

    if (planes_buf.len != 24 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&planes_buf);
        PyBuffer_Release(&aabb_buf);
        PyErr_SetString(PyExc_ValueError, "planes must be 24 floats");
        return NULL;
    }

    Py_ssize_t num_objects = aabb_buf.len / (6 * (Py_ssize_t)sizeof(float));
    const float *planes_f = (const float *)planes_buf.buf;
    const float *aabb_f = (const float *)aabb_buf.buf;

    Frustum frustum;
    for (int i = 0; i < 6; i++) {
        frustum.planes[i].nx = planes_f[i * 4 + 0];
        frustum.planes[i].ny = planes_f[i * 4 + 1];
        frustum.planes[i].nz = planes_f[i * 4 + 2];
        frustum.planes[i].d  = planes_f[i * 4 + 3];
    }

    PyObject *result = PyByteArray_FromStringAndSize(NULL, num_objects);
    if (!result) {
        PyBuffer_Release(&planes_buf);
        PyBuffer_Release(&aabb_buf);
        return NULL;
    }

    char *visibility = PyByteArray_AS_STRING(result);

    for (Py_ssize_t i = 0; i < num_objects; i++) {
        const float *bb = &aabb_f[i * 6];
        float minx = bb[0], miny = bb[1], minz = bb[2];
        float maxx = bb[3], maxy = bb[4], maxz = bb[5];

        int visible = 1;
        for (int j = 0; j < 6; j++) {
            const Plane *p = &frustum.planes[j];
            /* Positive vertex (furthest in normal direction) */
            float pvx = (p->nx >= 0.0f) ? maxx : minx;
            float pvy = (p->ny >= 0.0f) ? maxy : miny;
            float pvz = (p->nz >= 0.0f) ? maxz : minz;

            if (p->nx * pvx + p->ny * pvy + p->nz * pvz + p->d < 0.0f) {
                visible = 0;
                break;
            }
        }
        visibility[i] = (char)visible;
    }

    PyBuffer_Release(&planes_buf);
    PyBuffer_Release(&aabb_buf);
    return result;
}

/* --------------------------------------------------------------------------
 * compute_node_world_transforms(local_transforms, parent_indices, root_transform)
 *
 * Computes world-space transforms for a flattened node hierarchy by walking
 * the parent index chain.  Nodes MUST be sorted in topological order
 * (parent before child) so each node's parent is already computed.
 *
 * local_transforms: bytes of N×16 floats (column-major mat4 per node)
 * parent_indices:   bytes of N int32     (-1 = root node)
 * root_transform:   bytes of 16 floats   (column-major)
 *
 * Returns: bytes of N×16 floats  (world-space transforms, column-major)
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_compute_node_world_transforms(PyObject *self, PyObject *args) {
    Py_buffer locals_buf, parents_buf, root_buf;

    if (!PyArg_ParseTuple(args, "y*y*y*", &locals_buf, &parents_buf, &root_buf)) {
        return NULL;
    }

    if (root_buf.len != 16 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&locals_buf);
        PyBuffer_Release(&parents_buf);
        PyBuffer_Release(&root_buf);
        PyErr_SetString(PyExc_ValueError, "root_transform must be 16 floats");
        return NULL;
    }

    Py_ssize_t num_nodes = locals_buf.len / (16 * (Py_ssize_t)sizeof(float));
    if (locals_buf.len != num_nodes * 16 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&locals_buf);
        PyBuffer_Release(&parents_buf);
        PyBuffer_Release(&root_buf);
        PyErr_SetString(PyExc_ValueError, "local_transforms must be N×16 floats");
        return NULL;
    }

    if (parents_buf.len != num_nodes * (Py_ssize_t)sizeof(int)) {
        PyBuffer_Release(&locals_buf);
        PyBuffer_Release(&parents_buf);
        PyBuffer_Release(&root_buf);
        PyErr_SetString(PyExc_ValueError, "parent_indices length must match node count");
        return NULL;
    }

    const float *locals = (const float *)locals_buf.buf;
    const int *parents = (const int *)parents_buf.buf;
    const float *root = (const float *)root_buf.buf;

    Py_ssize_t result_size = num_nodes * 16 * (Py_ssize_t)sizeof(float);
    PyObject *result = PyBytes_FromStringAndSize(NULL, result_size);
    if (!result) {
        PyBuffer_Release(&locals_buf);
        PyBuffer_Release(&parents_buf);
        PyBuffer_Release(&root_buf);
        return NULL;
    }

    float *out = (float *)PyBytes_AS_STRING(result);

    for (Py_ssize_t i = 0; i < num_nodes; i++) {
        int parent_idx = parents[i];
        const float *parent_mat;
        if (parent_idx < 0 || parent_idx >= num_nodes) {
            parent_mat = root;
        } else {
            parent_mat = &out[parent_idx * 16];
        }
        mat4_mul(parent_mat, &locals[i * 16], &out[i * 16]);
    }

    PyBuffer_Release(&locals_buf);
    PyBuffer_Release(&parents_buf);
    PyBuffer_Release(&root_buf);
    return result;
}

/* --------------------------------------------------------------------------
 * batch_transform_vertices_2d(vertices_xy, n_verts, cos_r, sin_r,
 *                             flip_x, flip_y, tx, ty)
 *
 * Applies flip -> rotate -> translate to N 2D vertices in one C pass.
 * Used by indoor builder for room label bounds and marquee selection.
 *
 * vertices_xy: bytes of N×2 floats (x, y pairs in local space)
 * cos_r, sin_r: precomputed cos/sin of rotation angle
 * flip_x, flip_y: boolean flip flags (0 or 1)
 * tx, ty: translation to add after rotation
 *
 * Returns: bytes of N×2 floats (world x, y pairs)
 *          + bytes of 4 floats (min_x, min_y, max_x, max_y) as AABB
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_batch_transform_vertices_2d(PyObject *self, PyObject *args) {
    Py_buffer verts_buf;
    float cos_r, sin_r, tx, ty;
    int flip_x, flip_y;

    if (!PyArg_ParseTuple(args, "y*ffppff",
                          &verts_buf, &cos_r, &sin_r,
                          &flip_x, &flip_y, &tx, &ty)) {
        return NULL;
    }

    Py_ssize_t n_verts = verts_buf.len / (2 * (Py_ssize_t)sizeof(float));
    if (verts_buf.len != n_verts * 2 * (Py_ssize_t)sizeof(float)) {
        PyBuffer_Release(&verts_buf);
        PyErr_SetString(PyExc_ValueError, "vertices must be N×2 floats");
        return NULL;
    }

    const float *in = (const float *)verts_buf.buf;

    /* Output: N×2 floats for transformed verts */
    Py_ssize_t out_size = n_verts * 2 * (Py_ssize_t)sizeof(float);
    PyObject *result = PyBytes_FromStringAndSize(NULL, out_size);
    if (!result) {
        PyBuffer_Release(&verts_buf);
        return NULL;
    }
    float *out = (float *)PyBytes_AS_STRING(result);

    float bmin_x = FLT_MAX, bmin_y = FLT_MAX;
    float bmax_x = -FLT_MAX, bmax_y = -FLT_MAX;

    for (Py_ssize_t i = 0; i < n_verts; i++) {
        float lx = in[i * 2];
        float ly = in[i * 2 + 1];

        /* flip */
        if (flip_x) lx = -lx;
        if (flip_y) ly = -ly;

        /* rotate */
        float rx = lx * cos_r - ly * sin_r;
        float ry = lx * sin_r + ly * cos_r;

        /* translate */
        float wx = rx + tx;
        float wy = ry + ty;

        out[i * 2]     = wx;
        out[i * 2 + 1] = wy;

        /* AABB update */
        if (wx < bmin_x) bmin_x = wx;
        if (wy < bmin_y) bmin_y = wy;
        if (wx > bmax_x) bmax_x = wx;
        if (wy > bmax_y) bmax_y = wy;
    }

    PyBuffer_Release(&verts_buf);

    /* Return tuple: (transformed_bytes, (min_x, min_y, max_x, max_y)) */
    PyObject *bounds = Py_BuildValue("(ffff)", bmin_x, bmin_y, bmax_x, bmax_y);
    if (!bounds) {
        Py_DECREF(result);
        return NULL;
    }

    PyObject *ret = PyTuple_New(2);
    if (!ret) {
        Py_DECREF(result);
        Py_DECREF(bounds);
        return NULL;
    }
    PyTuple_SET_ITEM(ret, 0, result);
    PyTuple_SET_ITEM(ret, 1, bounds);
    return ret;
}


/* --------------------------------------------------------------------------
 * batch_hook_snap_distances(
 *     test_hooks_world,     -- bytes of M×2 floats (world x,y of test hooks)
 *     existing_hooks_world, -- bytes of K×2 floats (world x,y of existing hooks)
 *     existing_hook_rooms,  -- bytes of K int32 (room index for each existing hook)
 *     test_hook_local,      -- bytes of M×2 floats (local x,y offsets of test hooks)
 *     position_xy,          -- 2 floats: current position being snapped
 *     snap_threshold         -- float: max distance to consider
 * )
 *
 * For each pair (test_hook i, existing_hook j):
 *   snapped_pos = existing_hooks_world[j] - test_hook_local[i]
 *   distance = |position - snapped_pos|
 *
 * Returns tuple: (best_distance, best_test_idx, best_existing_idx,
 *                 snap_x, snap_y)  or None if no snap found.
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_batch_hook_snap_distances(PyObject *self, PyObject *args) {
    Py_buffer existing_hooks_buf, test_local_buf;
    float pos_x, pos_y, snap_threshold;

    if (!PyArg_ParseTuple(args, "y*y*fff",
                          &existing_hooks_buf, &test_local_buf,
                          &pos_x, &pos_y, &snap_threshold)) {
        return NULL;
    }

    Py_ssize_t n_existing = existing_hooks_buf.len / (2 * (Py_ssize_t)sizeof(float));
    Py_ssize_t n_test = test_local_buf.len / (2 * (Py_ssize_t)sizeof(float));

    const float *existing = (const float *)existing_hooks_buf.buf;
    const float *test_local = (const float *)test_local_buf.buf;

    float best_dist = snap_threshold;
    Py_ssize_t best_test = -1, best_existing = -1;
    float best_sx = 0.0f, best_sy = 0.0f;
    float threshold_sq = snap_threshold * snap_threshold;

    for (Py_ssize_t t = 0; t < n_test; t++) {
        float tlx = test_local[t * 2];
        float tly = test_local[t * 2 + 1];

        for (Py_ssize_t e = 0; e < n_existing; e++) {
            float ewx = existing[e * 2];
            float ewy = existing[e * 2 + 1];

            /* Where test room must be placed for this hook alignment */
            float sx = ewx - tlx;
            float sy = ewy - tly;

            /* Squared distance from current position to snap candidate */
            float dx = pos_x - sx;
            float dy = pos_y - sy;
            float dsq = dx * dx + dy * dy;

            if (dsq < threshold_sq && dsq < best_dist * best_dist) {
                float d = sqrtf(dsq);
                if (d < best_dist) {
                    best_dist = d;
                    best_test = t;
                    best_existing = e;
                    best_sx = sx;
                    best_sy = sy;
                }
            }
        }
    }

    PyBuffer_Release(&existing_hooks_buf);
    PyBuffer_Release(&test_local_buf);

    if (best_test < 0) {
        Py_RETURN_NONE;
    }

    return Py_BuildValue("(fnnff)", best_dist, best_test, best_existing,
                         best_sx, best_sy);
}


/* --------------------------------------------------------------------------
 * batch_vertices_in_rect(vertices_xy, n_verts, cos_r, sin_r,
 *                        flip_x, flip_y, tx, ty,
 *                        rect_min_x, rect_min_y, rect_max_x, rect_max_y)
 *
 * Transforms N local-space 2D vertices via flip->rotate->translate and
 * returns 1 if ANY vertex falls inside the given axis-aligned rect.
 * Early-terminates on first hit.  Used for marquee room selection.
 *
 * Returns: int (1 if any vertex inside rect, 0 otherwise)
 * -------------------------------------------------------------------------- */

static PyObject *
gl_accel_batch_vertices_in_rect(PyObject *self, PyObject *args) {
    Py_buffer verts_buf;
    float cos_r, sin_r, tx, ty;
    float rmin_x, rmin_y, rmax_x, rmax_y;
    int flip_x, flip_y;

    if (!PyArg_ParseTuple(args, "y*ffppffffff",
                          &verts_buf, &cos_r, &sin_r,
                          &flip_x, &flip_y, &tx, &ty,
                          &rmin_x, &rmin_y, &rmax_x, &rmax_y)) {
        return NULL;
    }

    Py_ssize_t n_verts = verts_buf.len / (2 * (Py_ssize_t)sizeof(float));
    const float *in = (const float *)verts_buf.buf;
    int found = 0;

    for (Py_ssize_t i = 0; i < n_verts; i++) {
        float lx = in[i * 2];
        float ly = in[i * 2 + 1];
        if (flip_x) lx = -lx;
        if (flip_y) ly = -ly;
        float wx = lx * cos_r - ly * sin_r + tx;
        float wy = lx * sin_r + ly * cos_r + ty;
        if (wx >= rmin_x && wx <= rmax_x && wy >= rmin_y && wy <= rmax_y) {
            found = 1;
            break;
        }
    }

    PyBuffer_Release(&verts_buf);
    return PyLong_FromLong(found);
}


/* --------------------------------------------------------------------------
 * Module definition
 * -------------------------------------------------------------------------- */

static PyMethodDef GlAccelMethods[] = {
    {"batch_frustum_cull", gl_accel_batch_frustum_cull, METH_VARARGS,
     "Batch frustum cull: test N spheres against 6 planes.\n\n"
     "Args:\n"
     "    planes: bytes of 24 floats (6 planes × 4 components each)\n"
     "    spheres: bytes of N×4 floats (cx, cy, cz, radius per object)\n\n"
     "Returns:\n"
     "    bytearray of N bytes (1=visible, 0=culled)"},

    {"extract_frustum_planes", gl_accel_extract_frustum_planes, METH_VARARGS,
     "Extract and normalize 6 frustum planes from a view-projection matrix.\n\n"
     "Args:\n"
     "    vp_matrix: bytes of 16 floats (4×4 column-major)\n\n"
     "Returns:\n"
     "    bytes of 24 floats (6 normalized planes)"},

    {"transform_bounds", gl_accel_transform_bounds, METH_VARARGS,
     "Compute AABB of vertices transformed by a matrix.\n\n"
     "Args:\n"
     "    vertex_data: bytes-like vertex buffer\n"
     "    vertex_count: int\n"
     "    stride: int (bytes per vertex)\n"
     "    pos_offset: int (byte offset to xyz position)\n"
     "    matrix: bytes of 16 floats (4×4 column-major)\n\n"
     "Returns:\n"
     "    tuple((min_x, min_y, min_z), (max_x, max_y, max_z))"},

    {"batch_sphere_distances", gl_accel_batch_sphere_distances, METH_VARARGS,
     "Compute minimum distance from each sphere to the nearest frustum plane.\n\n"
     "Args:\n"
     "    planes: bytes of 24 floats\n"
     "    spheres: bytes of N×4 floats\n\n"
     "Returns:\n"
     "    bytes of N floats"},

    {"mat4_multiply_batch", gl_accel_mat4_multiply_batch, METH_VARARGS,
     "Multiply N 4×4 matrices by a parent matrix.\n\n"
     "Args:\n"
     "    transforms: bytes of N×16 floats\n"
     "    parent_matrix: bytes of 16 floats\n\n"
     "Returns:\n"
     "    bytes of N×16 floats"},

    {"aabb_in_frustum_batch", gl_accel_aabb_in_frustum_batch, METH_VARARGS,
     "Batch AABB frustum test: test N AABBs against 6 planes.\n\n"
     "Args:\n"
     "    planes: bytes of 24 floats\n"
     "    aabbs: bytes of N×6 floats (min_x, min_y, min_z, max_x, max_y, max_z)\n\n"
     "Returns:\n"
     "    bytearray of N bytes (1=visible, 0=culled)"},

    {"compute_node_world_transforms", gl_accel_compute_node_world_transforms, METH_VARARGS,
     "Compute world-space transforms for a flattened node hierarchy.\n\n"
     "Nodes must be in topological order (parent index < own index).\n\n"
     "Args:\n"
     "    local_transforms: bytes of N×16 floats (column-major mat4 per node)\n"
     "    parent_indices: bytes of N int32 (-1 for root nodes)\n"
     "    root_transform: bytes of 16 floats (column-major root transform)\n\n"
     "Returns:\n"
     "    bytes of N×16 floats (world-space transforms)"},

    {"batch_transform_vertices_2d", gl_accel_batch_transform_vertices_2d, METH_VARARGS,
     "Batch transform N 2D vertices: flip -> rotate -> translate.\n\n"
     "Args:\n"
     "    vertices: bytes of N×2 floats (local x,y pairs)\n"
     "    cos_r, sin_r: floats (precomputed rotation)\n"
     "    flip_x, flip_y: booleans\n"
     "    tx, ty: floats (translation)\n\n"
     "Returns:\n"
     "    tuple(bytes of N×2 floats, (min_x, min_y, max_x, max_y))"},

    {"batch_hook_snap_distances", gl_accel_batch_hook_snap_distances, METH_VARARGS,
     "Find best hook snap among all test×existing hook pairs.\n\n"
     "Args:\n"
     "    existing_hooks: bytes of K×2 floats (world x,y)\n"
     "    test_local: bytes of M×2 floats (local offsets)\n"
     "    pos_x, pos_y: current position floats\n"
     "    snap_threshold: float\n\n"
     "Returns:\n"
     "    tuple(dist, test_idx, existing_idx, snap_x, snap_y) or None"},

    {"batch_vertices_in_rect", gl_accel_batch_vertices_in_rect, METH_VARARGS,
     "Test if any local-space vertex transforms into an axis-aligned rect.\n\n"
     "Args:\n"
     "    vertices: bytes of N×2 floats\n"
     "    cos_r, sin_r: floats\n"
     "    flip_x, flip_y: booleans\n"
     "    tx, ty: floats\n"
     "    rect_min_x, rect_min_y, rect_max_x, rect_max_y: floats\n\n"
     "Returns:\n"
     "    int (1 if any vertex inside rect, 0 otherwise)"},

    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef gl_accel_module = {
    PyModuleDef_HEAD_INIT,
    "_gl_accel",
    "C acceleration for PyKotor GL rendering pipeline.\n\n"
    "Provides batch frustum culling, transform bounds computation,\n"
    "and matrix multiplication for the module designer render loop.",
    -1,
    GlAccelMethods
};

PyMODINIT_FUNC
PyInit__gl_accel(void) {
    return PyModule_Create(&gl_accel_module);
}
