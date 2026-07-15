class MicroserviceDatabaseRouter:
    """
    A router to control all database operations on models in the
    microservice applications to isolate them to their respective databases.
    """

    # Map Django app labels directly to their corresponding database names.
    APP_DB_MAPPING = {
        'users': 'user_db',
        'doctors': 'user_db',
        'patients': 'user_db',
        'schedules': 'user_db',
        'bookings': 'booking_db',
        'auth': 'user_db',
        'contenttypes': 'user_db',
        'admin': 'user_db',
        'sessions': 'user_db',
        'token_blacklist': 'user_db',
    }

    def db_for_read(self, model, **hints):
        """
        Attempts to read models go to their respective databases.
        """
        return self.APP_DB_MAPPING.get(model._meta.app_label)

    def db_for_write(self, model, **hints):
        """
        Attempts to write models go to their respective databases.
        """
        return self.APP_DB_MAPPING.get(model._meta.app_label)

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations if both models are in the same database.
        """
        db_obj1 = self.APP_DB_MAPPING.get(obj1._meta.app_label)
        db_obj2 = self.APP_DB_MAPPING.get(obj2._meta.app_label)
        if db_obj1 and db_obj2:
            return db_obj1 == db_obj2
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Ensure that the models only appear in their respective databases.
        """
        target_db = self.APP_DB_MAPPING.get(app_label)
        if target_db:
            return db == target_db
        return False

    