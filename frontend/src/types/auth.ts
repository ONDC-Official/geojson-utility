
export interface User {
  name: string;
}
export interface login {
  token: string;
  user: string;
}

export interface LoginCredentials {
  token: string;
}


export interface AuthContextType {
  user: User | null;
  token: string | null;
  login: any
  logout: () => void;
  isAuthenticated: boolean;
}
