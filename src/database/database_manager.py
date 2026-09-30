import psycopg2


class DatabaseManager:
    """
    Manages PostgreSQL database connections and basic database operations.
    """

    def __init__(self, config):
        self.config = config
        self.connection = None

    def connect(self):
        """
        Establish PostgreSQL connection.
        """

        if self.connection is not None:
            return self.connection

        db_config = self.config.get_database_config()

        self.connection = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"]
        )

        return self.connection

    def close(self):
        """
        Close database connection.
        """

        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def execute(self, query, params=None):
        """
        Execute INSERT, UPDATE, DELETE or DDL query.
        """

        connection = self.connect()

        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    def fetch_all(self, query, params=None):
        """
        Execute SELECT query and return all rows.
        """

        connection = self.connect()

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def fetch_one(self, query, params=None):
        """
        Execute SELECT query and return one row.
        """

        connection = self.connect()

        with connection.cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchone()

    def table_count(self, table_name):
        """
        Return number of rows in a table.
        """

        query = f"SELECT COUNT(*) FROM {table_name}"

        result = self.fetch_one(query)

        return result[0]