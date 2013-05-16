# -*- coding: utf-8 -*-

# Implementation of a key-value store API.

db.define_table('key_value_store',
    Field('content', 'text'))


def keystore_write(v):
    """Writes a new string v to the key-value store, returning the string key."""
    id = db.key_value_store.insert(content = v)
    logger.info("inserting keystore key " + str(id) + " value " + str(v)[:20])
    return str(id)


def keystore_read(k, default=None):
    """Returns the string read from the keystore for a key k."""
    logger.info("Reading keystore key " + str(k))
    try:
        id = int(k)
    except ValueError:
        return default
    except TypeError:
        return default
    v = db.key_value_store(id)
    if v is None:
        return default
    return v.content


def keystore_multi_read(k_list, default=None):
    """Gets a list of keys to read and a default value, and returns a dictionary
    mapping every key to the value read, using the default value if the value could
    not be found."""
    logger.info("Reading keystore keys: %r" % k_list)
    r = {}
    for k in k_list:
        v = keystore_read(k, default=default)
        r[k] = v
    return r


def keystore_update(k, v):
    """Updates the keystore, replacing the previous value for key k
    (if any) with value v.  If the key k is invalid, creates a new key. 
    It returns the key that has been used."""
    logger.info("Updating keystore for key " + str(k) + " and value: " + str(v)[:20])
    try:
        id = int(k)
    except ValueError:
        id = db.key_value_store.insert(content = v)
        return str(id)
    except TypeError:
        id = db.key_value_store.insert(content = v)
        return str(id)
    db.key_value_store.update_or_insert(db.key_value_store.id == id, content = v)
    return k


def keystore_delete(k):
    """Deletes the entry for key k, if present."""
    logger.info("Requesting deletion of keystore key " + str(k))
    try:
        id = int(k)
    except ValueError:
        return
    except TypeError:
        return
    db(db.key_value_store.id == id).delete()
