Work with pyAndorSDK3 

# Aquisition_automatic
Used to acquire multiple sets of frames that are then saved for posterior analysis.

## Comments for me
1000 frames is possible, on the other hand a million will rende this error message:

    buf = np.empty((imgsize,), dtype='B') # "B" es uint8
    numpy.core._exceptions._ArrayMemoryError: Unable to allocate 1.42 MiB for an array with shape (1490400,) and data type uint8
