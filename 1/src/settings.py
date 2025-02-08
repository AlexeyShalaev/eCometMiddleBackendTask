import os


class EnvSettings:
    def __init__(self):
        for attr, attr_type in self.__class__.__annotations__.items():
            env_value = os.getenv(attr)
            if env_value:
                try:
                    # TODO: Add more type conversions
                    value = attr_type(env_value)
                    setattr(self, attr, value)
                except ValueError:
                    raise ValueError(
                        f"Cannot convert environment variable {attr} to {attr_type}"
                    )
            else:
                # Check if there is a default value in the class
                if hasattr(self.__class__, attr):
                    default_value = getattr(self.__class__, attr)
                    setattr(self, attr, default_value)
                else:
                    # If no default and no environment variable, raise an error
                    raise ValueError(
                        f"Environment variable for {attr} is not provided and no default value is set."
                    )
