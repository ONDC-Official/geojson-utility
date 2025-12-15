
export interface User {
  username: string;
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
  login: (token: string, user: User) => void;
  logout: () => void;
  isAuthenticated: boolean;
}
