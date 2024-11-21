#Copyright © Amazon.com and Affiliates: This deliverable is considered Developed Content as defined in the AWS Service Terms and the SOW between the parties dated 15 Nov 2024.
import boto3
import json
import urllib.request

s3 = boto3.client('s3')

def send_response(event, context, response_status, reason=None, response_data=None, physical_resource_id=None):
    response_body = json.dumps({
        'Status': response_status,
        'Reason': reason or 'See the details in CloudWatch Log Stream: ' + context.log_stream_name,
        'PhysicalResourceId': physical_resource_id or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': response_data or {}
    })

    print("Response body being sent to CloudFormation:")
    print(response_body)

    req = urllib.request.Request(
        url=event['ResponseURL'],
        data=response_body.encode('utf-8'),
        headers={
            'Content-Length': str(len(response_body)),
            'Content-Type': 'application/json',
        },
        method='PUT'
    )

    try:
        with urllib.request.urlopen(req) as response:
            print(f"Response sent to CloudFormation: {response.read().decode()}")
            print(f"Status code: {response.getcode()}")
            print(f"Status message: {response.msg}")
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} - {e.reason}")
        print(f"Response URL: {event['ResponseURL']}")
        print(f"Failed to send response1: {e.read().decode()}")
    except urllib.error.URLError as e:
        print(f"URLError: Failed to reach server: {e.reason}")
    except Exception as e:
        print(f"General Exception: Failed to send response1: {str(e)}")

def lambda_handler(event, context):
    try:
        print("Event received:", event)
        if event['RequestType'] == 'Create' or event['RequestType'] == 'Update':
            dest_bucket = event['ResourceProperties']['DestBucket']
            print(f"Destination bucket: {dest_bucket}")
            
            # List of files to copy
            files_to_copy = ['awsnews.xml', 'processed.xml', 'testnews.xml']
            
            for file_name in files_to_copy:
                print(f"Copying file: {file_name}")
                try:
                    with open(file_name, 'rb') as file:
                        s3.put_object(Bucket=dest_bucket, Key=file_name, Body=file.read())
                    print(f"Successfully copied {file_name}")
                except Exception as e:
                    print(f"Error copying {file_name}: {str(e)}")
                    raise
            
            print("All files copied successfully")
        
        send_response(event, context, 'SUCCESS')
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
        send_response(event, context, 'FAILED', reason=str(e))
