from pyspark.sql import SparkSession
from pyspark.sql.functions import col
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Initializing SparkSession for Data Quality Check")
    spark = SparkSession.builder \
        .appName("Data Quality Check") \
        .getOrCreate()
        
    try:
        # Dummy logic for demonstration
        logger.info("Reading data for quality check...")
        data = [
            ("user_1", "john@example.com", 25),
            ("user_2", None, 30),
            ("user_3", "invalid_email", -5),
            ("user_4", "jane@example.com", 28),
        ]
        columns = ["user_id", "email", "age"]
        df = spark.createDataFrame(data, columns)
        
        logger.info("Running Data Quality Rules...")
        
        # Rule 1: Email should not be null
        null_emails = df.filter(col("email").isNull()).count()
        if null_emails > 0:
            logger.warning(f"Data Quality Warning: Found {null_emails} records with null email.")
            
        # Rule 2: Age should be positive
        negative_ages = df.filter(col("age") < 0).count()
        if negative_ages > 0:
            logger.warning(f"Data Quality Warning: Found {negative_ages} records with negative age.")
            
        logger.info("Data Quality Check completed.")
        
    except Exception as e:
        logger.error(f"Job failed: {e}")
        raise
    finally:
        spark.stop()

if __name__ == "__main__":
    main()
