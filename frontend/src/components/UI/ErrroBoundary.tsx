import React from 'react';
import { Banner } from '@neo4j-ndl/react';

export default class ErrorBoundary extends React.Component<any, any> {
  state = { hasError: false, errorMessage: '', errorName: '' };

  static getDerivedStateFromError(_error: unknown) {
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    this.setState({ ...this.state, errorMessage: error.message, errorName: error.name });
    console.log({ error });
    console.log({ errorInfo });
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className='n-size-full n-flex n-flex-col n-items-center n-justify-center n-rounded-md n-bg-palette-neutral-bg-weak n-box-border'>
          <Banner
            icon
            type='info'
            description={
              this.state.errorMessage === 'Missing required parameter client_id.'
                ? 'Please Provide The Google Client ID For GCS Source'
                : this.state.errorName === 'InvalidCharacterError'
                ? 'Please Clear the Local Storage'
                : 'Sorry there was a problem loading this page'
            }
            title='Something went wrong'
            floating
            className='mt-8'
            actions={
              this.state.errorName === 'InvalidCharacterError'
                ? [
                    {
                      label: 'Clear local storage',
                      onClick: () => {
                        localStorage.clear();
                        window.location.reload();
                      },
                    },
                  ]
                : [
                    {
                      label: 'Documentation',
                      href: 'https://github.com/neo4j-labs/llm-graph-builder',
                      target: '_blank',
                    },
                  ]
            }
          ></Banner>
        </div>
      );
    }
    return this.props.children;
  }
}
