"""The options the admin page can change. Each can still start from its environment variable; a saved value wins."""

from settings import Setting

SETTINGS = [
    Setting("update_check_hours", "Check for updates every (hours)", "float", 6.0, "TEM_UPDATE_CHECK_HOURS", 0, 720,
            help="0 = only when you press Check now. The weights are one pinned file, so this only finds a missing file"),
    Setting("max_inflight", "Calls allowed to wait for the model", "int", 0, "TEM_MAX_INFLIGHT", 0, 10000,
            help="Per replica; more get 429. 0 = 4"),
    Setting("cache_size", "Answers kept per replica", "int", 32, "TEM_CACHE_SIZE", 0, 100000,
            help="Images made with a seed, sent again for the same class, steps, step size and seed. Each is at most 1 MB. 0 = off"),
    Setting("max_steps", "Most Langevin steps per image", "int", 120, "TEM_MAX_STEPS", 1, 1000,
            help="A call asking for more gets 422. The paper uses 60; each step costs about 0.1 s on a laptop GPU"),
    Setting("device", "Device", "text", "cuda", "TEM_DEVICE", restart=True, blank=False,
            help="cuda for the GPU (about 4 GB of memory per replica), cpu only for tests: it takes minutes per image"),
    Setting("warm", "Load the model at start", "bool", True, "TEM_WARM", restart=True),
]
