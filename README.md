# s3-hooked

s3 proxy written in Python/aiohttp that supports flexible integrations via hooks to
achieve things like symmetric encryption (built-in), validations, virus scanning,
triggering webhooks etc.

## Pluggable Hooks

The proxy forwards all traffic to the configured S3-store.

When uploading and downloading you can inject hooks in three categories:
 `pre_upload_before_check` that will be called before upload simultaneously
 `pre_upload_unsafe` that will be called before upload but after
    `pre_upload_before_check` has run successfully. You can run calls on the content
    here that will actually interpret the data, assuming the previous call has checked
    for malignous data.
 `post_upload` will run after the upload has run successfully. It will not change the
    existing state. Consider it side-effects.

Hooks are named with the function name by default. This can be overriden when register-
ing.

The default hooks for encryption/decryption are `hook_encrypt_data` and 
`hook_decrypt_data` respectively. If you override the hooks in your implementation 
you should import them from the `proxy.default_hooks` module. You may of course
override those, too.

Every hook should take the current request plus optionally data or other params and
return a tuple of the name, boolen of success and optionally resulting data or 
the error message on failure.

Per event all registered hooks must pass in order to proceed. If a hook fails the
proxy will return an error message with name and reason.
To register a procedure as a hook wrap it in a hook-function that takes
the request and binary data.

Unless overridden hooks will be read from `proxy.default_hooks`. Hooks are overridden
by placing decorated functions in the `plugin_hooks/hooks.py` file. If you want to
keep the default encryption mechanism import them event from `proxy.default_hooks`.
If you wish to override them import the events from `proxy.events` directly.

The `pos` parameter for registering hooks is only relevant if the registered hooks
should be called in a predefined order, i. e. on an event that waits for each hook
to be finished (i. e. `blocking=True`)


## Incldued addon dependencies

The `INSTALL_ADDONS` build arg (true/false) controls whether to install the following extra
dependencies (default: true)

 - `python-clamd`
 - `python-magic`



## start the development server

```
docker compose up -d --build 
```

This will pull up a local instance on :8080

It will also create a minio service on :9000
