#import "PythonBridge.h"
#import "NativeFonts.h"
#include <Python/Python.h>

static PyObject *fontRequest(PyObject *self, PyObject *arguments) {
    const char *json;
    if (!PyArg_ParseTuple(arguments, "s", &json)) return NULL;
    NSError *error = nil;
    NSString *result = EXPFontRequest(@(json), &error);
    if (!result) {
        PyErr_SetString(PyExc_ValueError, error.localizedDescription.UTF8String ?: "Native font failed");
        return NULL;
    }
    return PyUnicode_FromString(result.UTF8String);
}

static PyMethodDef platformMethods[] = {{"font", fontRequest, METH_VARARGS, "Native system-font metrics and atlas"}, {NULL}};
static struct PyModuleDef platformModule = {PyModuleDef_HEAD_INIT, "exp_platform", NULL, -1, platformMethods};
static PyObject *platformInit(void) { return PyModule_Create(&platformModule); }

static NSError *bridgeError(NSString *message) {
    return [NSError errorWithDomain:@"org.expruntime.python" code:1
                          userInfo:@{NSLocalizedDescriptionKey: message}];
}

static NSString *pythonError(void) {
    PyObject *exception = PyErr_GetRaisedException();
    if (exception) PyErr_DisplayException(exception);
    PyObject *description = exception ? PyObject_Str(exception) : NULL;
    const char *text = description ? PyUnicode_AsUTF8(description) : NULL;
    NSString *message = text ? [NSString stringWithUTF8String:text] : @"Python operation failed";
    Py_XDECREF(description);
    Py_XDECREF(exception);
    PyErr_Clear();
    return message;
}

@implementation PythonBridge

- (BOOL)initializePython:(NSError **)error {
    if (Py_IsInitialized()) return YES;
    if (PyImport_AppendInittab("exp_platform", platformInit) != 0) {
        if (error) *error = bridgeError(@"Cannot register native platform services");
        return NO;
    }
    NSString *root = NSBundle.mainBundle.resourcePath;
    PyPreConfig preconfig;
    PyPreConfig_InitIsolatedConfig(&preconfig);
    preconfig.utf8_mode = 1;
    PyStatus status = Py_PreInitialize(&preconfig);
    if (PyStatus_Exception(status)) {
        if (error) *error = bridgeError(@(status.err_msg ?: "Python preinitialization failed"));
        return NO;
    }
    PyConfig config;
    PyConfig_InitIsolatedConfig(&config);
    config.buffered_stdio = 0;
    config.write_bytecode = 0;
    config.install_signal_handlers = 0;
    config.module_search_paths_set = 1;
    status = PyConfig_SetBytesString(&config, &config.home,
                                     [root stringByAppendingPathComponent:@"python"].UTF8String);
    if (!PyStatus_Exception(status)) {
        for (NSString *relative in @[@"python/lib/python3.14", @"python/lib/python3.14/lib-dynload",
                                     @"app", @"app_packages"]) {
            wchar_t *path = Py_DecodeLocale([root stringByAppendingPathComponent:relative].UTF8String, NULL);
            if (!path) { status = PyStatus_NoMemory(); break; }
            status = PyWideStringList_Append(&config.module_search_paths, path);
            PyMem_RawFree(path);
            if (PyStatus_Exception(status)) break;
        }
    }
    if (!PyStatus_Exception(status)) status = Py_InitializeFromConfig(&config);
    NSString *message = PyStatus_Exception(status) ? @(status.err_msg ?: "Python initialization failed") : nil;
    PyConfig_Clear(&config);
    if (message) {
        if (error) *error = bridgeError(message);
        return NO;
    }
    // The serial dispatch queue can move between OS threads. Acquire the GIL
    // around every call, and release it while the app is idle or suspended.
    PyEval_SaveThread();
    return YES;
}

- (NSString *)request:(NSString *)json directory:(NSString *)directory error:(NSError **)error {
    if (![self initializePython:error]) return nil;
    PyGILState_STATE gil = PyGILState_Ensure();
    PyObject *module = PyImport_ImportModule("exp_runtime.platforms.ios");
    PyObject *handler = module ? PyObject_GetAttrString(module, "request") : NULL;
    PyObject *response = handler ? PyObject_CallFunction(handler, "ss", json.UTF8String, directory.UTF8String) : NULL;
    const char *utf8 = response ? PyUnicode_AsUTF8(response) : NULL;
    NSString *result = utf8 ? [NSString stringWithUTF8String:utf8] : nil;
    if (!result && error) *error = bridgeError(pythonError());
    Py_XDECREF(response);
    Py_XDECREF(handler);
    Py_XDECREF(module);
    PyGILState_Release(gil);
    return result;
}
@end
