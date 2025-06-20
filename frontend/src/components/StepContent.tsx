import React, { useEffect, useState } from "react";
import { Button, Upload, Progress, message, Typography, Spin } from "antd";
import {
  DownloadOutlined,
  UploadOutlined,
  FileTextOutlined,
} from "@ant-design/icons";
import type { UploadFile, UploadProps } from "antd";
import { useAuth } from "../contexts/AuthContext";
import {
  StepCard,
  InstructionList,
  InstructionListItem,
  UploadSection,
} from "./StyledComponents";
import axios from "axios";

const { Title, Paragraph } = Typography;

interface StepContentProps {
  currentStep: number;
  onSignInClick: () => void;
  setCurrentStep: React.Dispatch<React.SetStateAction<number>>;
}

const StepContent: React.FC<StepContentProps> = ({
  currentStep,
  onSignInClick,
  setCurrentStep,
}) => {
  const { isAuthenticated, token, logout } = useAuth();
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [next, setNext] = useState(false);
  const [result, setResult] = useState("");
  const [id, setId] = useState(null);
  let interval: NodeJS.Timeout;

  const apiUrl = import.meta.env.VITE_API_BASE_URL;
  useEffect(() => {
    setNext(false);
    setUploading(false);
  }, []);

  const onNextClick = () => {
    setCurrentStep(3);
    test(id);
  };
  const handleDownloadCSV = async () => {
    try {
      const response = await axios.get(`${apiUrl}/catchment/sample-csv`, {
        responseType: "blob",
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "sample.csv"); // optional custom name
      document.body.appendChild(link);
      link.click();
      link.remove();

      message.success("CSV file downloaded successfully!");
    } catch (error) {
      if (error.response && error.response.status === 401) {
        message.error("Session expired. Please log in again.");
        logout();
      } else {
        console.error("Download failed", error);
      }
    }
  };

  const onDownloadSCV = async () => {
    try {
      const response = await axios.get(
        `${apiUrl}/catchment/csv/${id}`,

        {
          headers: {
            responseType: "blob",
            Authorization: `Bearer ${token}`,
          },
        }
      );

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "sample.csv");
      document.body.appendChild(link);
      link.click();
      link.remove();

      message.success("CSV file downloaded successfully!");
    } catch (error) {
      if (error.response && error.response.status === 401) {
        message.error("Session expired. Please log in again.");
        logout();
      } else {
        message.error("Download failed");
      }
    }
  };

  const uploadProps: UploadProps = {
    name: "file",
    accept: ".csv",
    beforeUpload: async (file) => {
      if (!isAuthenticated) {
        message.error("Please sign in to upload files");
        return false;
      }

      const isCsv =
        file.type === "text/csv" || file.name.toLowerCase().endsWith(".csv");
      if (!isCsv) {
        message.error("You can only upload CSV files!");
        return false;
      }

      // Read the file content to validate structure
      const fileText = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result as string);
        reader.onerror = () => reject("Error reading file");
        reader.readAsText(file);
      });

      const lines = fileText
        .split(/\r\n|\n/)
        .filter((line) => line.trim() !== "");

      // Basic CSV format check (at least 1 header + 1 data row)
      if (lines.length < 2) {
        message.error("CSV must have a header and at least one data row.");
        return false;
      }

      // Optionally: check if all rows have the same number of columns
      const columnCount = lines[0].split(",").length;
      const invalidRows = lines.filter(
        (line) => line.split(",").length !== columnCount
      );

      // Simulate upload progress
      setUploading(true);
      setUploadProgress(0);

      const formData = new FormData();

      formData.append("file", file);
      try {
        const response = await axios.post(
          `${apiUrl}/catchment/bulk`,
          formData,
          {
            headers: {
              "Content-Type": "multipart/form-data",
              Authorization: `Bearer ${token}`,
            },
            onUploadProgress: (progressEvent) => {
              const percent = Math.round(
                (progressEvent.loaded * 100) / 1
                // (progressEvent.loaded * 100) / (progressEvent.total || 1)
              );
              setUploadProgress(percent);
            },
          }
        );

        if (response) {
          message.success("File uploaded successfully!");
          const id = response?.data?.csv_id;
          setId(id);
          setResult("pending");
          setNext(true);
        }
      } catch (error: any) {
        if (error.response?.status === 401) {
          message.error("Session expired. Please log in again.");
          logout();
        } else {
          message.error("File upload failed.");
        }
      }

      return false; // prevent default upload
    },
    onRemove: () => {
      setUploadProgress(0);
      setUploading(false);
    },
  };

  const test = async (id: string) => {
    const fetchStatus = async () => {
      try {
        const response = await axios.get(
          `${apiUrl}/catchment/csv-status/${id}`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
          }
        );
        const status = response.data.status?.toLowerCase();

        if (status === "done" || status === "complete") {
          setResult("done");
          clearInterval(interval);
          message.success("CSV Processed successfully!");
        } else if (status === "failed" || status === "fail") {
          clearInterval(interval);
          message.error("Something went wrong!");
          setResult("fail");
        }
      } catch (error) {
        if (error.response && error.response.status === 401) {
          message.error("Session expired. Please log in again.");
          logout();
        } else {
          message.error("Facing some issue while fetching file status");
        }
      }
    };

    // Initial call
    fetchStatus();

    // Poll every 5 seconds
    const interval = setInterval(fetchStatus, 5000);

    // Cleanup on unmount
    return () => clearInterval(interval);
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0:
        return (
          <StepCard title="Instructions" extra={<FileTextOutlined />}>
            <Paragraph>
              Welcome to the ONDC GeoJson Processing Tool. Follow these simple
              steps to get started:
            </Paragraph>
            <InstructionList>
              <InstructionListItem>
                Use the token received via email to login and access all
                features
              </InstructionListItem>
              <InstructionListItem>
                Download the sample CSV template from Step 2
              </InstructionListItem>
              <InstructionListItem>
                Prepare your data according to the template format, Use the
                defined GeoJson and update your store serviceability in your
                catalog
              </InstructionListItem>
              <InstructionListItem>
                Upload your CSV file in Step 3 for processing and Click on
                Continue button to generate CSV
              </InstructionListItem>

              <InstructionListItem>
                Once processing is complete, download the final CSV file
              </InstructionListItem>
            </InstructionList>
            {!isAuthenticated && (
              <div style={{ textAlign: "center", marginTop: "24px" }}>
                <Button
                  type="primary"
                  size="large"
                  onClick={onSignInClick}
                  style={{
                    background:
                      "linear-gradient(90deg, #1c75bc, #4aa1e0 51%, #1c75bc) var(--x, 100%) / 200%",
                    color: "#fff",
                  }}
                >
                  Sign In to Continue
                </Button>
              </div>
            )}
          </StepCard>
        );

      case 1:
        return (
          <StepCard title="Download CSV Template" extra={<DownloadOutlined />}>
            <>
              <Paragraph>
                Download the CSV template to understand the required data
                format. This template includes sample data and column headers.
              </Paragraph>
              <div style={{ textAlign: "center", marginTop: "24px" }}>
                <Button
                  type="primary"
                  size="large"
                  icon={<DownloadOutlined />}
                  onClick={handleDownloadCSV}
                  style={{
                    background:
                      "linear-gradient(90deg, #1c75bc, #4aa1e0 51%, #1c75bc) var(--x, 100%) / 200%",
                    color: "#fff",
                  }}
                >
                  Download Sample CSV
                </Button>
              </div>
            </>
          </StepCard>
        );

      case 2:
        return (
          <StepCard title="Upload Your CSV File" extra={<UploadOutlined />}>
            {isAuthenticated ? (
              <>
                <Paragraph>
                  Upload your prepared CSV file. Make sure it follows the format
                  from the downloaded template.
                </Paragraph>
                <UploadSection>
                  <Upload.Dragger
                    {...uploadProps}
                    maxCount={1}
                    multiple={false}
                    showUploadList={{ showRemoveIcon: true }}
                  >
                    <p className="ant-upload-drag-icon">
                      <UploadOutlined
                        style={{ fontSize: "48px", color: "#1890ff" }}
                      />
                    </p>
                    <p className="ant-upload-text">
                      Click or drag CSV file to this area to upload
                    </p>
                    <p className="ant-upload-hint">
                      Only CSV files are supported. Maximum file size: 10MB
                    </p>
                  </Upload.Dragger>
                </UploadSection>
                {uploading && (
                  <div style={{ marginTop: "24px" }}>
                    <Progress
                      percent={uploadProgress}
                      status={uploadProgress === 100 ? "success" : "active"}
                    />
                  </div>
                )}
                {next && (
                  <div className="flex items-baseline justify-end">
                    <Button
                      type="primary"
                      onClick={onNextClick}
                      style={{
                        background:
                          "linear-gradient(90deg, #1c75bc, #4aa1e0 51%, #1c75bc) var(--x, 100%) / 200%",
                        color: "#fff",
                      }}
                    >
                      Next
                    </Button>
                  </div>
                )}
              </>
            ) : (
              <div style={{ textAlign: "center", padding: "40px" }}>
                <Title level={4}>Authentication Required</Title>
                <Paragraph>Please sign in to upload CSV files.</Paragraph>
                <Button
                  type="primary"
                  onClick={onSignInClick}
                  style={{
                    background:
                      "linear-gradient(90deg, #1c75bc, #4aa1e0 51%, #1c75bc) var(--x, 100%) / 200%",
                    color: "#fff",
                  }}
                >
                  Sign In
                </Button>
              </div>
            )}
          </StepCard>
        );
      case 3:
        return (
          <StepCard title="Generate CSV" extra={<UploadOutlined />}>
            {
              <>
                {next && (
                  <div className="flex items-baseline justify-between">
                    <Paragraph>
                      {result === "pending" ? (
                        <>
                          "Generating the processed CSV file"
                          <Spin size="small" />
                        </>
                      ) : result === "fail" ? (
                        "Failed to generate the CSV file. Please try again later or contact support if the issue persists."
                      ) : (
                        "Now you can download you csv file by clicking on download button here"
                      )}
                    </Paragraph>
                    {result === "done" && (
                      <Button
                        type="primary"
                        onClick={onDownloadSCV}
                        style={{
                          background:
                            "linear-gradient(90deg, #1c75bc, #4aa1e0 51%, #1c75bc) var(--x, 100%) / 200%",
                          color: "#fff",
                        }}
                      >
                        Download processed CSV
                      </Button>
                    )}
                  </div>
                )}
              </>
            }
          </StepCard>
        );

      default:
        return null;
    }
  };

  return renderStepContent();
};

export default StepContent;
