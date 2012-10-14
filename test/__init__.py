def make_callback(key, history):
    def callback(*args):
        history.append(key)
    return callback
