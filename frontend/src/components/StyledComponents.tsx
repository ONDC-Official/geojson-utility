import { Layout, Card } from "antd";
import React from "react";

export const StyledHeader: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => (
  <Layout.Header className="bg-white px-6 shadow-md flex items-center justify-between fixed top-0 w-full z-[1000]">
    {children}
  </Layout.Header>
);

export const LogoContainer: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => (
  <div className="flex items-center text-2xl font-bold text-blue-500">
    {children}
  </div>
);

export const LogoImage: React.FC<{ src: string; alt: string }> = ({
  src,
  alt,
}) => <img src={src} alt={alt} className="h-10 mr-3" />;

export const MainContent: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => (
  <Layout.Content
    className="mt-2 p-10 min-h-[calc(100vh-64px)]"
    style={{
      background: "linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%)",
    }}
  >
    {children}
  </Layout.Content>
);

export const ContentContainer: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => <div className="max-w-6xl mx-auto p-5">{children}</div>;

export const StepsContainer: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => (
  <div className="my-10 bg-white p-10 rounded-xl shadow-lg ">{children}</div>
);

interface StepCardProps {
  title: string;
  extra?: React.ReactNode;
  children: React.ReactNode;
}

export const StepCard: React.FC<StepCardProps> = ({
  title,
  extra,
  children,
}) => (
  <Card
    title={title}
    extra={extra}
    className="mt-8 rounded-lg shadow-sm"
    bodyStyle={{ padding: "32px" }}
  >
    {children}
  </Card>
);

export const InstructionList: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => <ul className="list-none p-0 my-6">{children}</ul>;

export const InstructionListItem: React.FC<{
  title: string;
  children: React.ReactNode;
}> = ({ title, children }) => (
  <li className="py-3 border-b border-gray-100 flex items-start last:border-b-0">
    <span className="text-green-500 font-bold mr-3 w-5 text-center mt-1">
      ✓
    </span>
    <div>
      <div className="font-semibold text-gray-800">{title}</div>
      <div className="text-gray-600 text-sm mt-1">{children}</div>
    </div>
  </li>
);

export const UploadSection: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => (
  <div className="text-center p-10 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300 my-6 hover:border-blue-500 hover:bg-blue-50 transition-colors">
    {children}
  </div>
);
