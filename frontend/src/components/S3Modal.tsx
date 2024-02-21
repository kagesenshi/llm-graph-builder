import { TextInput, Button, Dialog, Banner } from '@neo4j-ndl/react';
import React, { useState } from 'react';
import { S3ModalProps } from '../types';
import { bucketScanAPI } from '../services/BucketScan';
import { useCredentials } from '../context/UserCredentials';
import { getSourceNodes } from '../services/getFiles';
import { getFileFromLocal } from '../utils/utils';
import { useFileContext } from '../context/UsersFiles';
import { v4 as uuidv4 } from 'uuid';

interface SourceNode {
  fileName: string;
  fileSize: number;
  fileType?: string;
  nodeCount?: number;
  processingTime?: string;
  relationshipCount?: number;
  model: string;
  status: string;
  s3url?: string;
}

const S3Modal: React.FC<S3ModalProps> = ({ hideModal, open }) => {
  const [bucketUrl, setBucketUrl] = useState<string>('');
  const [accessKey, setAccessKey] = useState<string>('');
  const [secretKey, setSecretKey] = useState<string>('');

  const [status, setStatus] = useState<'unknown' | 'success' | 'info' | 'warning' | 'danger'>('unknown');
  const [statusMessage, setStatusMessage] = useState<string>('');
  const { userCredentials } = useCredentials();
  const { setFiles, setFilesData } = useFileContext();
  const changeHandler = (e: any) => {
    setBucketUrl(e.target.value);
  };
  const submitHandler = async (bucketUrl: string) => {
    if (accessKey.length) {
      sessionStorage.setItem('accesskey', accessKey);
    }
    if (secretKey.length) {
      sessionStorage.setItem('secretkey', secretKey);
    }
    if (bucketUrl.trim() != '') {
      try {
        setStatus('info');
        setStatusMessage('Scaning...');
        const apiResponse = await bucketScanAPI(bucketUrl, userCredentials, accessKey, secretKey);
        console.log('response', apiResponse);
        setStatus('success');
        setStatusMessage(`Successfully Created Source Nodes For ${apiResponse.data.success_count} Files`);
        setBucketUrl('');
        const res: any = await getSourceNodes();
        if (Array.isArray(res.data.data) && res.data.data.length) {
          const prefiles = res.data.data.map((item: SourceNode) => ({
            name: item.fileName,
            size: item.fileSize ?? 0,
            type: item?.fileType?.toUpperCase() ?? 'None',
            NodesCount: item?.nodeCount ?? 0,
            processing: item?.processingTime ?? 'None',
            relationshipCount: item?.relationshipCount ?? 0,
            status:
              item?.s3url?.trim() != '' && item.status != 'Complted'
                ? 'New'
                : getFileFromLocal(`${item.fileName}`) == null && item?.status != 'Completed'
                ? 'Unavailable'
                : item.status,
            model: item?.model ?? 'Diffbot',
            id: uuidv4(),
            s3url: item.s3url ?? '',
          }));
          setFilesData(prefiles);
          const prefetchedFiles: any[] = [];
          res.data.data.forEach((item: any) => {
            const localFile = getFileFromLocal(`${item.fileName}`);
            if (localFile != null) {
              prefetchedFiles.push(localFile);
            } else {
              prefetchedFiles.push(null);
            }
          });
          setFiles(prefetchedFiles);
        }
      } catch (error) {
        setStatus('danger');
        setStatusMessage('Some Error Occurred');
      }
    } else {
      setStatus('warning');
      setStatusMessage('Please Fill The Bucket URL');
    }

    setTimeout(() => {
      hideModal();
    }, 2000);
  };
  return (
    <Dialog size='small' open={open} disableCloseButton>
      <Dialog.Content className='n-flex n-flex-col n-gap-token-4'>
        {status != 'unknown' && (
          <Banner
            closeable
            description={statusMessage}
            onClose={function closeHandler() {
              setStatus('unknown');
            }}
            type={status}
          />
        )}
        <div className='n-flex n-flex-row n-flex-wrap'>
          <div style={{ width: '100%', marginRight: '2.5%', display: 'inline-block' }}>
            <TextInput
              id='url'
              value={bucketUrl}
              disabled={false}
              label='Bucket URL'
              placeholder='s3://data.neo4j.com/pdf/'
              autoFocus
              fluid
              required
              onChange={(e) => {
                changeHandler(e);
              }}
            />
          </div>
          <div className='flex justify-between items-center w-full gap-4 mt-3'>
            <TextInput
              id='url'
              value={accessKey}
              disabled={false}
              label='Access Key'
              className='w-full'
              placeholder=''
              autoFocus
              fluid
              required
              isOptional
              onChange={(e) => {
                setAccessKey(e.target.value);
              }}
            />
            <TextInput
              id='url'
              value={secretKey}
              disabled={false}
              label='Secret Key'
              className='w-full'
              placeholder=''
              autoFocus
              fluid
              required
              isOptional
              onChange={(e) => {
                setSecretKey(e.target.value);
              }}
            />
          </div>
        </div>
        <Dialog.Actions className='mt-4'>
          <Button
            color='neutral'
            fill='outlined'
            onClick={() => {
              hideModal();
            }}
            size='medium'
          >
            Cancel
          </Button>
          <Button onClick={() => submitHandler(bucketUrl)} size='medium'>
            Submit
          </Button>
        </Dialog.Actions>
      </Dialog.Content>
    </Dialog>
  );
};
export default S3Modal;
