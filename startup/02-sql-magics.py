from IPython.core.magic import register_cell_magic
from IPython.display import display


@register_cell_magic
def sql(line, cell):
    try:
        from pyspark.sql import SparkSession

        spark = SparkSession.getActiveSession()
        if spark is None:
            return "No active Spark session found. Create one first."

        result = spark.sql(cell)

        # Add limit if not already in query
        if "limit" not in cell.lower():
            result = result.limit(1000)  # Safety limit

        df_pandas = result.toPandas()
        display(df_pandas)

    except Exception as e:
        return f"Error: {e}"

