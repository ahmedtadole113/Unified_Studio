from pyspark.sql import SparkSession
from pyspark.sql.functions import sum, col, current_date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Initializing SparkSession for Daily Sales Aggregation")
    spark = SparkSession.builder \
        .appName("Daily Sales Aggregation") \
        .getOrCreate()
        
    try:
        # Dummy logic for demonstration
        logger.info("Reading raw sales data from bronze zone...")
        data = [
            ("2023-10-01", "store_1", 100.50),
            ("2023-10-01", "store_2", 250.00),
            ("2023-10-01", "store_1", 50.25),
        ]
        columns = ["date", "store_id", "amount"]
        df = spark.createDataFrame(data, columns)
        
        logger.info("Performing aggregations...")
        agg_df = df.groupBy("date", "store_id").agg(sum("amount").alias("total_sales"))
        
        logger.info("Writing aggregated data to silver zone...")
        agg_df.show()
        
        logger.info("Daily Sales Aggregation completed successfully.")
        
    except Exception as e:
        logger.error(f"Job failed: {e}")
        raise
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
